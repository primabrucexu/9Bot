from __future__ import annotations

from datetime import date, timedelta
import logging
import re
from typing import Any

import akshare as ak
import pandas as pd

from app import db
from app.config import Settings
from app.services import indicators


logger = logging.getLogger(__name__)


class MarketDataError(Exception):
    pass


_SYMBOL_PATTERN = re.compile(r"^\d{6}$")
_SYMBOL_NAME_COLUMNS = {
    "代码": "symbol",
    "名称": "name",
}
_HISTORY_COLUMNS = {
    "日期": "trade_date",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
}
_INDEX_HISTORY_COLUMNS = {
    "date": "trade_date",
    "open": "open",
    "close": "close",
    "high": "high",
    "low": "low",
    "volume": "volume",
}
_BASE_UNIVERSE_PREFIXES = ("000", "001", "002", "003", "600", "601", "603", "605")
_FULL_A_SHARE_UNIVERSE_RULES = (
    {"prefixes": ("600", "601", "603", "605"), "market": "SSE", "board": "main"},
    {"prefixes": ("688", "689"), "market": "SSE", "board": "star"},
    {"prefixes": ("000", "001", "002", "003"), "market": "SZSE", "board": "main"},
    {"prefixes": ("300", "301"), "market": "SZSE", "board": "chinext"},
    {
        "prefixes": (
            "430",
            "440",
            "830",
            "831",
            "832",
            "833",
            "834",
            "835",
            "836",
            "837",
            "838",
            "839",
            "870",
            "871",
            "872",
            "873",
            "874",
            "875",
            "876",
            "877",
            "878",
            "879",
            "920",
        ),
        "market": "BSE",
        "board": "beijing",
    },
)
_MARKET_OVERVIEW_INDEXES = (
    {"symbol": "sh000001", "name": "上证指数"},
    {"symbol": "sz399001", "name": "深证成指"},
    {"symbol": "sz399006", "name": "创业板指"},
)
_DEFAULT_MARKET_SYNC_HISTORY_DAYS = 30
_MAX_MARKET_SYNC_HISTORY_DAYS = 3650
_FULL_MARKET_SYNC_SCOPE = "full-a-share"


def normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip()
    if not _SYMBOL_PATTERN.fullmatch(normalized):
        raise MarketDataError("股票代码格式不正确，请输入 6 位 A 股代码。")
    return normalized


def add_watchlist_symbol(settings: Settings, symbol: str) -> dict[str, Any]:
    stock = get_base_universe_stock(symbol)
    if stock is None:
        raise MarketDataError("仅支持上证、深证范围内且名称不含 ST 的股票。")

    db.add_watchlist_item(settings.database_path, stock["symbol"], stock["name"])
    logger.info(
        "Watchlist add stored symbol=%s name=%s database_path=%s",
        stock["symbol"],
        stock["name"],
        settings.database_path,
    )
    return stock


def remove_watchlist_symbol(settings: Settings, symbol: str) -> None:
    normalized = normalize_symbol(symbol)
    existing = db.get_watchlist_item(settings.database_path, normalized)
    if not existing:
        raise MarketDataError("该股票不在自选股列表中。")
    db.delete_watchlist_item(settings.database_path, normalized)


# Legacy path kept during migration.
def sync_watchlist_daily_bars(settings: Settings) -> list[dict[str, Any]]:
    watchlist = db.list_watchlist(settings.database_path)
    if not watchlist:
        raise MarketDataError("请先添加至少一只自选股，再同步日线数据。")

    logger.info(
        "Syncing watchlist daily bars database_path=%s watchlist_count=%s",
        settings.database_path,
        len(watchlist),
    )
    refreshed: list[dict[str, Any]] = []

    for item in watchlist:
        symbol = item["symbol"]
        logger.info("Syncing symbol=%s database_path=%s", symbol, settings.database_path)
        history = _fetch_history(symbol, settings.history_days)
        name = resolve_symbol_name(symbol)
        db.update_watchlist_name(settings.database_path, symbol, name)
        db.upsert_daily_bars(settings.database_path, symbol, history)
        last_trade_date = history.iloc[-1]["trade_date"].strftime("%Y-%m-%d") if not history.empty else None
        refreshed.append(
            {
                "symbol": symbol,
                "name": name,
                "bars": len(history),
                "last_trade_date": last_trade_date,
            }
        )
        logger.info(
            "Synced symbol=%s name=%s bars=%s last_trade_date=%s database_path=%s",
            symbol,
            name,
            len(history),
            last_trade_date,
            settings.database_path,
        )

    return refreshed


def refresh_stock_universe(settings: Settings) -> dict[str, Any]:
    snapshot = _fetch_stock_snapshot()
    universe = _build_full_a_share_universe(snapshot)
    count = db.upsert_stock_universe(settings.database_path, universe.to_dict("records"))
    logger.info(
        "Refreshed stock universe database_path=%s count=%s",
        settings.database_path,
        count,
    )
    return {
        "scope": _FULL_MARKET_SYNC_SCOPE,
        "count": count,
    }


def sync_universe_daily_bars(
    settings: Settings,
    *,
    history_days: int = _DEFAULT_MARKET_SYNC_HISTORY_DAYS,
    symbols: list[str] | None = None,
    refresh_universe: bool = False,
) -> dict[str, Any]:
    resolved_history_days = _resolve_history_days(history_days)
    if refresh_universe or not db.list_stock_universe(settings.database_path, limit=1):
        refresh_stock_universe(settings)

    targets = _resolve_universe_sync_targets(settings.database_path, symbols)
    if not targets:
        raise MarketDataError("请先刷新全市场股票清单，再同步历史数据。")

    logger.info(
        "Syncing universe daily bars database_path=%s history_days=%s universe_count=%s",
        settings.database_path,
        resolved_history_days,
        len(targets),
    )
    db.replace_market_sync_state(settings.database_path, _FULL_MARKET_SYNC_SCOPE, status="running")

    synced_count = 0
    last_trade_date: str | None = None
    latest_trade_day: date | None = None

    try:
        for item in targets:
            symbol = item["symbol"]
            logger.info(
                "Syncing universe symbol=%s database_path=%s history_days=%s",
                symbol,
                settings.database_path,
                resolved_history_days,
            )
            history = _fetch_history(symbol, resolved_history_days)
            db.upsert_daily_bars(settings.database_path, symbol, history)
            synced_count += 1
            if not history.empty:
                current_trade_day = history.iloc[-1]["trade_date"].date()
                if latest_trade_day is None or current_trade_day > latest_trade_day:
                    latest_trade_day = current_trade_day
                    last_trade_date = current_trade_day.strftime("%Y-%m-%d")
    except Exception as exc:
        db.replace_market_sync_state(
            settings.database_path,
            _FULL_MARKET_SYNC_SCOPE,
            status="failed",
            last_trade_date=last_trade_date,
            error=str(exc),
        )
        raise

    db.replace_market_sync_state(
        settings.database_path,
        _FULL_MARKET_SYNC_SCOPE,
        status="succeeded",
        last_trade_date=last_trade_date,
        error=None,
    )
    logger.info(
        "Synced universe daily bars database_path=%s history_days=%s synced_count=%s last_trade_date=%s",
        settings.database_path,
        resolved_history_days,
        synced_count,
        last_trade_date,
    )
    return {
        "scope": _FULL_MARKET_SYNC_SCOPE,
        "history_days": resolved_history_days,
        "universe_count": len(targets),
        "synced_count": synced_count,
        "last_trade_date": last_trade_date,
    }


def build_watchlist_rows(settings: Settings) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in db.list_watchlist(settings.database_path):
        bars = db.get_daily_bars(settings.database_path, item["symbol"], limit=120)
        summary = indicators.summarize_latest(bars)
        rows.append(
            {
                "symbol": item["symbol"],
                "name": item["name"],
                "last_close": summary.get("close"),
                "daily_change_pct": summary.get("daily_change_pct"),
                "ma_status": _build_ma_status(summary),
                "macd_bias": summary.get("macd_bias", "未同步"),
                "rsi_state": summary.get("rsi_state", "未同步"),
                "last_trade_date": summary.get("trade_date"),
                "signals": summary.get("signals", []),
                "has_data": bool(summary),
            }
        )
    return rows


def build_market_overview(settings: Settings) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    history_limit = max(settings.history_days, 120)

    for item in _MARKET_OVERVIEW_INDEXES:
        bars = _fetch_index_history(item["symbol"], history_limit)
        summary = indicators.summarize_latest(bars)
        if not summary:
            raise MarketDataError(f"{item['name']} 暂无可用历史行情。")
        rows.append(
            {
                "symbol": item["symbol"],
                "name": item["name"],
                "summary": summary,
            }
        )

    return rows


def list_base_universe(query: str = "", limit: int = 50, offset: int = 0) -> dict[str, Any]:
    universe = _filter_base_universe(_fetch_stock_snapshot())
    keyword = query.strip()
    if keyword:
        universe = universe[
            universe["symbol"].str.contains(keyword, regex=False, na=False)
            | universe["name"].str.contains(re.escape(keyword), case=False, regex=True, na=False)
        ]

    total = len(universe)
    rows = universe.iloc[offset : offset + limit][["symbol", "name"]].to_dict("records")
    return {
        "rows": rows,
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def get_base_universe_stock(symbol: str) -> dict[str, str] | None:
    normalized = normalize_symbol(symbol)
    universe = _filter_base_universe(_fetch_stock_snapshot())
    matched = universe.loc[universe["symbol"] == normalized, ["symbol", "name"]]
    if matched.empty:
        return None

    record = matched.iloc[0]
    return {
        "symbol": str(record["symbol"]),
        "name": str(record["name"]),
    }


def resolve_symbol_name(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    try:
        name_map = _fetch_symbol_name_map()
    except MarketDataError as exc:
        logger.info("Resolve symbol name fallback symbol=%s error=%s", normalized, exc)
        return normalized

    resolved = name_map.get(normalized)
    if not resolved:
        logger.info("Symbol name not found in metadata, fallback to symbol=%s", normalized)
        return normalized
    return resolved


def _fetch_symbol_name_map() -> dict[str, str]:
    snapshot = _fetch_stock_snapshot()
    return snapshot.set_index("symbol")["name"].to_dict()


def _fetch_stock_snapshot() -> pd.DataFrame:
    try:
        snapshot = ak.stock_zh_a_spot_em()
    except Exception as exc:  # pragma: no cover - depends on upstream service
        raise MarketDataError(f"获取股票名称失败：{exc}") from exc

    if snapshot.empty:
        raise MarketDataError("股票名称数据为空，稍后再试。")

    missing_columns = [column for column in _SYMBOL_NAME_COLUMNS if column not in snapshot.columns]
    if missing_columns:
        raise MarketDataError(f"股票名称字段缺失：{', '.join(missing_columns)}")

    normalized = snapshot.rename(columns=_SYMBOL_NAME_COLUMNS)[list(_SYMBOL_NAME_COLUMNS.values())].copy()
    normalized["symbol"] = normalized["symbol"].astype(str).str.zfill(6)
    normalized["name"] = normalized["name"].astype(str).str.strip()
    normalized = normalized.dropna(subset=["symbol", "name"])
    normalized = normalized[normalized["name"].astype(bool)]
    normalized = normalized.drop_duplicates(subset=["symbol"], keep="first")
    normalized = normalized.sort_values("symbol").reset_index(drop=True)
    return normalized


def _filter_base_universe(snapshot: pd.DataFrame) -> pd.DataFrame:
    filtered = snapshot[
        snapshot["symbol"].str.startswith(_BASE_UNIVERSE_PREFIXES)
        & ~snapshot["name"].str.contains("ST", case=False, regex=False, na=False)
    ].copy()
    return filtered.reset_index(drop=True)


def _build_full_a_share_universe(snapshot: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in snapshot.to_dict("records"):
        symbol = str(item["symbol"])
        classification = _classify_a_share_symbol(symbol)
        if classification is None:
            continue
        name = str(item["name"])
        rows.append(
            {
                "symbol": symbol,
                "name": name,
                "market": classification["market"],
                "board": classification["board"],
                "is_st": _is_st_stock_name(name),
                "is_active": True,
            }
        )

    if not rows:
        raise MarketDataError("未识别到可用 A 股股票清单。")

    universe = pd.DataFrame(rows)
    universe = universe.drop_duplicates(subset=["symbol"], keep="first")
    return universe.sort_values("symbol").reset_index(drop=True)


def _classify_a_share_symbol(symbol: str) -> dict[str, str] | None:
    for rule in _FULL_A_SHARE_UNIVERSE_RULES:
        if symbol.startswith(rule["prefixes"]):
            return {
                "market": rule["market"],
                "board": rule["board"],
            }
    return None


def _is_st_stock_name(name: str) -> bool:
    return "ST" in name.upper()


def _resolve_universe_sync_targets(database_path, symbols: list[str] | None) -> list[dict[str, Any]]:
    if not symbols:
        return db.list_stock_universe(database_path, active_only=True)

    targets: list[dict[str, Any]] = []
    for raw_symbol in symbols:
        symbol = normalize_symbol(raw_symbol)
        item = db.get_stock_universe_item(database_path, symbol)
        if item is None:
            raise MarketDataError(f"{symbol} 不在全市场股票清单中，请先刷新股票清单。")
        targets.append(item)
    return targets


def _resolve_history_days(history_days: int) -> int:
    if history_days < 1:
        raise MarketDataError("history_days 必须大于 0。")
    if history_days > _MAX_MARKET_SYNC_HISTORY_DAYS:
        raise MarketDataError(f"history_days 不能超过 {_MAX_MARKET_SYNC_HISTORY_DAYS} 天。")
    return history_days


def _fetch_history(symbol: str, history_days: int) -> pd.DataFrame:
    end_date = date.today()
    start_date = end_date - timedelta(days=history_days)

    try:
        history = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            adjust="qfq",
        )
    except Exception as exc:  # pragma: no cover - depends on upstream service
        raise MarketDataError(f"获取 {symbol} 历史行情失败：{exc}") from exc

    if history.empty:
        raise MarketDataError(f"{symbol} 暂无可用历史行情。")

    return _normalize_history(history, _HISTORY_COLUMNS)


def _fetch_index_history(symbol: str, history_limit: int) -> pd.DataFrame:
    try:
        history = ak.stock_zh_index_daily(symbol=symbol)
    except Exception as exc:  # pragma: no cover - depends on upstream service
        raise MarketDataError(f"获取 {symbol} 指数行情失败：{exc}") from exc

    if history.empty:
        raise MarketDataError(f"{symbol} 暂无可用指数行情。")

    normalized = _normalize_history(history, _INDEX_HISTORY_COLUMNS)
    return normalized.tail(history_limit).reset_index(drop=True)


def _normalize_history(history: pd.DataFrame, column_mapping: dict[str, str]) -> pd.DataFrame:
    missing_columns = [column for column in column_mapping if column not in history.columns]
    if missing_columns:
        raise MarketDataError(f"历史行情字段缺失：{', '.join(missing_columns)}")

    normalized = history.rename(columns=column_mapping)[list(column_mapping.values())].copy()
    normalized["trade_date"] = pd.to_datetime(normalized["trade_date"])

    for column in ("open", "close", "high", "low", "volume"):
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    if "amount" in normalized.columns:
        normalized["amount"] = pd.to_numeric(normalized["amount"], errors="coerce")
    else:
        normalized["amount"] = pd.NA

    if "volume" not in normalized.columns:
        normalized["volume"] = pd.NA

    normalized = normalized.dropna(subset=["trade_date", "open", "close", "high", "low"])
    normalized = normalized.sort_values("trade_date").reset_index(drop=True)
    return normalized[["trade_date", "open", "close", "high", "low", "volume", "amount"]]


def _build_ma_status(summary: dict[str, Any]) -> str:
    if not summary:
        return "未同步"
    return "MA20 上方" if summary.get("is_above_ma20") else "MA20 下方"
