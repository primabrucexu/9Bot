from __future__ import annotations

from datetime import date, timedelta
import re
from typing import Any

import akshare as ak
import pandas as pd

from app import db
from app.config import Settings
from app.services import indicators


class MarketDataError(Exception):
    pass


_SYMBOL_PATTERN = re.compile(r"^\d{6}$")
_SNAPSHOT_COLUMNS = {
    "代码": "symbol",
    "名称": "name",
    "最新价": "latest_price",
    "涨跌幅": "change_pct",
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


def normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip()
    if not _SYMBOL_PATTERN.fullmatch(normalized):
        raise MarketDataError("股票代码格式不正确，请输入 6 位 A 股代码。")
    return normalized


def add_watchlist_symbol(settings: Settings, symbol: str) -> dict[str, Any]:
    normalized = normalize_symbol(symbol)
    quote = lookup_symbol(normalized)
    db.add_watchlist_item(settings.database_path, normalized, quote["name"])
    return quote


def remove_watchlist_symbol(settings: Settings, symbol: str) -> None:
    normalized = normalize_symbol(symbol)
    existing = db.get_watchlist_item(settings.database_path, normalized)
    if not existing:
        raise MarketDataError("该股票不在自选股列表中。")
    db.delete_watchlist_item(settings.database_path, normalized)


def refresh_watchlist(settings: Settings) -> list[dict[str, Any]]:
    watchlist = db.list_watchlist(settings.database_path)
    if not watchlist:
        raise MarketDataError("请先添加至少一只自选股，再刷新行情。")

    snapshot_table = _fetch_snapshot_table()
    refreshed: list[dict[str, Any]] = []

    for item in watchlist:
        symbol = item["symbol"]
        matching = snapshot_table.loc[snapshot_table["symbol"] == symbol]
        if matching.empty:
            raise MarketDataError(f"未找到股票代码 {symbol} 的实时行情。")

        snapshot = matching.iloc[0].to_dict()
        history = _fetch_history(symbol, settings.history_days)
        db.update_watchlist_name(settings.database_path, symbol, snapshot["name"])
        db.upsert_daily_bars(settings.database_path, symbol, history)
        refreshed.append({
            "symbol": symbol,
            "name": snapshot["name"],
            "bars": len(history),
        })

    return refreshed


def build_dashboard_rows(settings: Settings) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in db.list_watchlist(settings.database_path):
        bars = db.get_daily_bars(settings.database_path, item["symbol"], limit=120)
        summary = indicators.summarize_latest(bars)
        rows.append(
            {
                "symbol": item["symbol"],
                "name": item["name"],
                "latest_close": summary.get("close"),
                "daily_change_pct": summary.get("daily_change_pct"),
                "ma_status": _build_ma_status(summary),
                "macd_bias": summary.get("macd_bias", "未刷新"),
                "rsi_state": summary.get("rsi_state", "未刷新"),
                "last_trade_date": summary.get("trade_date"),
                "signals": summary.get("signals", []),
                "has_data": bool(summary),
            }
        )
    return rows


def lookup_symbol(symbol: str) -> dict[str, Any]:
    snapshot_table = _fetch_snapshot_table()
    matching = snapshot_table.loc[snapshot_table["symbol"] == symbol]
    if matching.empty:
        raise MarketDataError(f"未找到股票代码 {symbol}，请确认它是有效的 A 股代码。")
    row = matching.iloc[0]
    return {
        "symbol": row["symbol"],
        "name": row["name"],
        "latest_price": float(row["latest_price"]) if pd.notna(row["latest_price"]) else None,
        "change_pct": float(row["change_pct"]) if pd.notna(row["change_pct"]) else None,
    }


def _fetch_snapshot_table() -> pd.DataFrame:
    try:
        snapshot = ak.stock_zh_a_spot_em()
    except Exception as exc:  # pragma: no cover - depends on upstream service
        raise MarketDataError(f"获取实时行情失败：{exc}") from exc

    if snapshot.empty:
        raise MarketDataError("实时行情为空，稍后再试。")

    missing_columns = [column for column in _SNAPSHOT_COLUMNS if column not in snapshot.columns]
    if missing_columns:
        raise MarketDataError(f"实时行情字段缺失：{', '.join(missing_columns)}")

    normalized = snapshot.rename(columns=_SNAPSHOT_COLUMNS)[list(_SNAPSHOT_COLUMNS.values())].copy()
    normalized["symbol"] = normalized["symbol"].astype(str).str.zfill(6)
    for column in ("latest_price", "change_pct"):
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    return normalized


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

    missing_columns = [column for column in _HISTORY_COLUMNS if column not in history.columns]
    if missing_columns:
        raise MarketDataError(f"历史行情字段缺失：{', '.join(missing_columns)}")

    normalized = history.rename(columns=_HISTORY_COLUMNS)[list(_HISTORY_COLUMNS.values())].copy()
    normalized["trade_date"] = pd.to_datetime(normalized["trade_date"])
    for column in ("open", "close", "high", "low", "volume", "amount"):
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    normalized = normalized.dropna(subset=["trade_date", "open", "close", "high", "low"])
    normalized = normalized.sort_values("trade_date").reset_index(drop=True)
    return normalized


def _build_ma_status(summary: dict[str, Any]) -> str:
    if not summary:
        return "未刷新"
    return "MA20 上方" if summary.get("is_above_ma20") else "MA20 下方"
