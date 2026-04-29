from __future__ import annotations

from collections import Counter
from datetime import date
import logging
from typing import Any

import akshare as ak
import pandas as pd

from app.config import Settings
from app.services import indicators, market_data


logger = logging.getLogger(__name__)

_LIMIT_UP_COLUMNS = {
    "代码": "symbol",
    "名称": "name",
    "所属行业": "sector",
    "连板数": "board_count",
    "涨停统计": "limit_up_stats",
}


class StockScreenerError(Exception):
    pass


def screen_limit_up_copy(settings: Settings, limit: int = 10) -> dict[str, Any]:
    latest_trade_date = _resolve_latest_trade_date()
    last_10_trade_dates = _recent_trade_dates(latest_trade_date, 10)
    last_7_trade_dates = set(_recent_trade_dates(latest_trade_date, 7))
    trade_date_index = {trade_day: index for index, trade_day in enumerate(last_10_trade_dates)}

    universe = market_data._filter_base_universe(market_data._fetch_stock_snapshot())
    recent_limit_ups = _collect_recent_limit_ups(last_10_trade_dates, universe)
    if recent_limit_ups.empty:
        raise StockScreenerError("最近 10 个交易日没有可用涨停数据。")

    hot_sectors, sector_ranks = _build_hot_sectors(recent_limit_ups)
    candidates = recent_limit_ups[
        recent_limit_ups["trade_date"].isin(last_7_trade_dates)
        & recent_limit_ups["sector"].isin(sector_ranks)
    ].copy()
    if candidates.empty:
        raise StockScreenerError("最近 7 个交易日没有满足条件的热点涨停候选股。")

    rows: list[dict[str, Any]] = []
    history_days = max(120, min(settings.history_days, 180))

    for symbol, group in candidates.groupby("symbol"):
        try:
            history = market_data._fetch_history(symbol, history_days)
        except market_data.MarketDataError as exc:
            logger.warning("Skip screener symbol=%s error=%s", symbol, exc)
            continue

        row = _score_candidate(
            history,
            group.sort_values("trade_date"),
            sector_ranks,
            latest_trade_date,
            trade_date_index,
        )
        if row is not None:
            rows.append(row)

    if not rows:
        raise StockScreenerError("没有可用于排序的候选股，请稍后重试。")

    rows.sort(
        key=lambda item: (
            item["score"],
            item["limit_up_count_7d"],
            item["max_board_count"],
            item.get("daily_change_pct") or float("-inf"),
            item["symbol"],
        ),
        reverse=True,
    )
    trimmed_rows = rows[:limit]
    return {
        "trade_date": latest_trade_date.strftime("%Y-%m-%d"),
        "rows": trimmed_rows,
        "total": len(trimmed_rows),
        "limit": limit,
        "hot_sectors": hot_sectors,
    }


def _resolve_latest_trade_date(today: date | None = None) -> date:
    current = today or date.today()
    try:
        trade_calendar = ak.tool_trade_date_hist_sina()
    except Exception as exc:  # pragma: no cover - depends on upstream service
        raise StockScreenerError(f"获取交易日历失败：{exc}") from exc

    if trade_calendar.empty or "trade_date" not in trade_calendar.columns:
        raise StockScreenerError("交易日历数据不可用。")

    trade_dates = sorted(value for value in trade_calendar["trade_date"].tolist() if value <= current)
    if not trade_dates:
        raise StockScreenerError("没有可用交易日。")
    return trade_dates[-1]


def _recent_trade_dates(end_date: date, count: int) -> list[date]:
    try:
        trade_calendar = ak.tool_trade_date_hist_sina()
    except Exception as exc:  # pragma: no cover - depends on upstream service
        raise StockScreenerError(f"获取交易日历失败：{exc}") from exc

    if trade_calendar.empty or "trade_date" not in trade_calendar.columns:
        raise StockScreenerError("交易日历数据不可用。")

    trade_dates = [value for value in trade_calendar["trade_date"].tolist() if value <= end_date]
    if len(trade_dates) < count:
        raise StockScreenerError(f"最近 {count} 个交易日数据不足。")
    return trade_dates[-count:]


def _collect_recent_limit_ups(trade_dates: list[date], universe: pd.DataFrame) -> pd.DataFrame:
    merged_frames: list[pd.DataFrame] = []
    base_universe = universe[["symbol", "name"]].copy()

    for trade_date in trade_dates:
        pool = _fetch_limit_up_pool(trade_date)
        if pool.empty:
            continue
        merged = pool.merge(base_universe, on="symbol", how="inner", suffixes=("", "_base"))
        if merged.empty:
            continue
        merged["name"] = merged["name_base"].fillna(merged["name"])
        merged = merged.drop(columns=["name_base"])
        merged_frames.append(merged)

    if not merged_frames:
        return pd.DataFrame(columns=["trade_date", "symbol", "name", "sector", "board_count", "limit_up_stats"])
    return pd.concat(merged_frames, ignore_index=True)


def _fetch_limit_up_pool(trade_date: date) -> pd.DataFrame:
    try:
        pool = ak.stock_zt_pool_em(date=trade_date.strftime("%Y%m%d"))
    except Exception as exc:  # pragma: no cover - depends on upstream service
        raise StockScreenerError(f"获取 {trade_date:%Y-%m-%d} 涨停池失败：{exc}") from exc

    if pool.empty:
        return pd.DataFrame(columns=["trade_date", "symbol", "name", "sector", "board_count", "limit_up_stats"])

    missing_columns = [column for column in _LIMIT_UP_COLUMNS if column not in pool.columns]
    if missing_columns:
        raise StockScreenerError(f"涨停池字段缺失：{', '.join(missing_columns)}")

    normalized = pool.rename(columns=_LIMIT_UP_COLUMNS)[list(_LIMIT_UP_COLUMNS.values())].copy()
    normalized["symbol"] = normalized["symbol"].astype(str).str.zfill(6)
    normalized["name"] = normalized["name"].astype(str).str.strip()
    normalized["sector"] = normalized["sector"].astype(str).str.strip()
    normalized["board_count"] = pd.to_numeric(normalized["board_count"], errors="coerce").fillna(0).astype(int)
    normalized["limit_up_stats"] = normalized["limit_up_stats"].astype(str).str.strip()
    normalized = normalized.dropna(subset=["symbol", "name", "sector"])
    normalized = normalized[normalized["sector"].astype(bool)]
    normalized["trade_date"] = trade_date
    return normalized[["trade_date", "symbol", "name", "sector", "board_count", "limit_up_stats"]]


def _build_hot_sectors(limit_ups: pd.DataFrame) -> tuple[list[dict[str, Any]], dict[str, int]]:
    sector_counts = Counter(limit_ups["sector"].tolist())
    hot_sector_rows: list[dict[str, Any]] = []
    sector_ranks: dict[str, int] = {}

    for rank, (sector, count) in enumerate(sector_counts.most_common(5), start=1):
        hot_sector_rows.append({"name": sector, "count": int(count), "rank": rank})
        sector_ranks[sector] = rank

    if not hot_sector_rows:
        raise StockScreenerError("最近 10 个交易日没有可用热点板块数据。")
    return hot_sector_rows, sector_ranks


def _score_candidate(
    history: pd.DataFrame,
    candidate_limit_ups: pd.DataFrame,
    sector_ranks: dict[str, int],
    latest_trade_date: date,
    trade_date_index: dict[date, int],
) -> dict[str, Any] | None:
    if history.empty:
        return None

    enriched = indicators.add_indicators(history)
    if enriched.empty:
        return None

    latest = enriched.iloc[-1]
    previous = enriched.iloc[-2] if len(enriched) > 1 else latest
    last_limit_up_event = candidate_limit_ups.iloc[-1]
    last_limit_up_date = last_limit_up_event["trade_date"]
    limit_up_count = int(len(candidate_limit_ups))
    max_board_count = int(candidate_limit_ups["board_count"].max())
    sector = str(last_limit_up_event["sector"])
    sector_rank = sector_ranks[sector]

    reference_rows = enriched[enriched["trade_date"].dt.date == last_limit_up_date]
    if reference_rows.empty:
        return None
    reference_bar = reference_rows.iloc[-1]

    post_limit_bars = enriched[enriched["trade_date"].dt.date > last_limit_up_date].copy()
    pullback_bars = post_limit_bars.iloc[:-1] if len(post_limit_bars) > 1 else post_limit_bars
    avg_pullback_volume = pullback_bars["volume"].dropna().mean() if not pullback_bars.empty else pd.NA

    sector_score = _score_sector(sector_rank)
    limit_up_score = _score_limit_up_strength(
        latest_trade_date,
        last_limit_up_date,
        limit_up_count,
        max_board_count,
        trade_date_index,
    )
    trend_score = _score_trend(latest)
    pullback_score = _score_pullback(reference_bar, pullback_bars)
    relaunch_score = _score_relaunch(latest, previous, avg_pullback_volume)
    total_score = sector_score + limit_up_score + trend_score + pullback_score + relaunch_score

    summary = indicators.summarize_latest(history)
    if not summary:
        return None

    reasons = [f"热点板块第 {sector_rank} 名：{sector}", f"近 7 个交易日涨停 {limit_up_count} 次"]
    if max_board_count >= 2:
        reasons.append(f"期间最高连板 {max_board_count} 板")
    if trend_score >= 20:
        reasons.append("均线与 MACD 维持强势")
    if pullback_score >= 12:
        reasons.append("涨停后回调幅度与量能较健康")
    if relaunch_score >= 10:
        reasons.append("最新一日有再启动迹象")
    reasons.extend(summary.get("signals", []))

    return {
        "symbol": str(last_limit_up_event["symbol"]),
        "name": str(last_limit_up_event["name"]),
        "sector": sector,
        "score": int(total_score),
        "trade_date": summary["trade_date"],
        "last_close": summary["close"],
        "last_limit_up_date": last_limit_up_date.strftime("%Y-%m-%d"),
        "limit_up_count_7d": limit_up_count,
        "max_board_count": max_board_count,
        "daily_change_pct": summary.get("daily_change_pct"),
        "ma_status": "MA20 上方" if summary.get("is_above_ma20") else "MA20 下方",
        "macd_bias": summary.get("macd_bias", "数据不足"),
        "rsi_state": summary.get("rsi_state", "数据不足"),
        "signals": reasons[:6],
    }


def _score_sector(sector_rank: int) -> int:
    weights = {1: 20, 2: 16, 3: 12, 4: 8, 5: 4}
    return weights.get(sector_rank, 0)


def _score_limit_up_strength(
    latest_trade_date: date,
    last_limit_up_date: date,
    limit_up_count: int,
    max_board_count: int,
    trade_date_index: dict[date, int],
) -> int:
    latest_index = trade_date_index.get(latest_trade_date)
    last_limit_up_index = trade_date_index.get(last_limit_up_date)
    if latest_index is not None and last_limit_up_index is not None:
        trade_gap = max(latest_index - last_limit_up_index, 0)
    else:
        trade_gap = max((latest_trade_date - last_limit_up_date).days, 0)
    proximity_score = max(0, 12 - trade_gap * 2)
    frequency_score = min(limit_up_count * 4, 6)
    board_score = min(max_board_count * 2, 4)
    return min(proximity_score + frequency_score + board_score, 20)


def _score_trend(latest: pd.Series) -> int:
    score = 0
    ma5 = latest.get("ma5")
    ma10 = latest.get("ma10")
    ma20 = latest.get("ma20")
    macd = latest.get("macd")
    macd_signal = latest.get("macd_signal")

    if pd.notna(ma5) and pd.notna(ma10) and pd.notna(ma20):
        if ma5 >= ma10 >= ma20:
            score += 12
        elif ma5 >= ma10 and latest["close"] >= ma20:
            score += 7

        if latest["close"] >= ma10:
            score += 5
        elif latest["close"] >= ma20:
            score += 3

    if pd.notna(macd) and pd.notna(macd_signal) and macd >= macd_signal:
        score += 8
    return min(score, 25)


def _score_pullback(reference_bar: pd.Series, pullback_bars: pd.DataFrame) -> int:
    if pullback_bars.empty or pd.isna(reference_bar.get("close")):
        return 0

    reference_close = float(reference_bar["close"])
    if reference_close <= 0:
        return 0

    pullback_low = pullback_bars["low"].dropna().min()
    pullback_pct = (reference_close - pullback_low) / reference_close * 100 if pd.notna(pullback_low) else 0
    average_pullback_volume = pullback_bars["volume"].dropna().mean()
    reference_volume = reference_bar.get("volume")

    score = 0
    if 2 <= pullback_pct <= 8:
        score += 10
    elif 0 < pullback_pct <= 12:
        score += 6

    if pd.notna(average_pullback_volume) and pd.notna(reference_volume) and reference_volume > 0:
        volume_ratio = average_pullback_volume / reference_volume
        if volume_ratio <= 0.7:
            score += 10
        elif volume_ratio <= 0.9:
            score += 6

    return min(score, 20)


def _score_relaunch(latest: pd.Series, previous: pd.Series, avg_pullback_volume: float | Any) -> int:
    score = 0
    if latest["close"] > latest["open"] and latest["close"] >= previous["close"]:
        score += 7

    ma5 = latest.get("ma5")
    if pd.notna(ma5) and latest["close"] >= ma5:
        score += 3

    if pd.notna(avg_pullback_volume) and avg_pullback_volume > 0 and latest["volume"] >= avg_pullback_volume * 1.2:
        score += 5
    return min(score, 15)
