from __future__ import annotations

from typing import Any

import pandas as pd


def add_indicators(bars: pd.DataFrame) -> pd.DataFrame:
    if bars.empty:
        return bars.copy()

    enriched = bars.copy().sort_values("trade_date").reset_index(drop=True)
    close = enriched["close"].astype(float)

    for window in (5, 10, 20, 60):
        enriched[f"ma{window}"] = close.rolling(window=window).mean()

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    enriched["macd"] = ema12 - ema26
    enriched["macd_signal"] = enriched["macd"].ewm(span=9, adjust=False).mean()
    enriched["macd_hist"] = enriched["macd"] - enriched["macd_signal"]

    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    average_gain = gains.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    average_loss = losses.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = average_gain / average_loss.replace(0, pd.NA)
    enriched["rsi14"] = 100 - (100 / (1 + rs))

    return enriched


def build_signal_summary(bars: pd.DataFrame) -> list[str]:
    enriched = add_indicators(bars)
    if enriched.empty:
        return ["暂无历史数据，请先刷新行情。"]

    latest = enriched.iloc[-1]
    previous = enriched.iloc[-2] if len(enriched) > 1 else latest
    rolling_window = enriched.tail(20)
    signals: list[str] = []

    ma20 = latest.get("ma20")
    if pd.notna(ma20):
        if latest["close"] >= ma20:
            signals.append("收盘价位于 MA20 上方")
        else:
            signals.append("收盘价位于 MA20 下方")

    if pd.notna(latest.get("ma5")) and pd.notna(ma20):
        if latest["ma5"] >= ma20 and previous.get("ma5", ma20) < previous.get("ma20", ma20):
            signals.append("MA5 刚上穿 MA20")
        elif latest["ma5"] < ma20 and previous.get("ma5", ma20) >= previous.get("ma20", ma20):
            signals.append("MA5 刚下穿 MA20")
        elif latest["ma5"] >= ma20:
            signals.append("短线均线仍强于中期均线")
        else:
            signals.append("短线均线仍弱于中期均线")

    if pd.notna(latest.get("macd")) and pd.notna(latest.get("macd_signal")):
        if latest["macd"] >= latest["macd_signal"] and previous.get("macd", 0) < previous.get("macd_signal", 0):
            signals.append("MACD 刚形成金叉")
        elif latest["macd"] < latest["macd_signal"] and previous.get("macd", 0) >= previous.get("macd_signal", 0):
            signals.append("MACD 刚形成死叉")
        elif latest["macd"] >= latest["macd_signal"]:
            signals.append("MACD 保持多头结构")
        else:
            signals.append("MACD 保持空头结构")

    rsi14 = latest.get("rsi14")
    if pd.notna(rsi14):
        if rsi14 >= 70:
            signals.append("RSI 进入偏热区")
        elif rsi14 <= 30:
            signals.append("RSI 进入偏冷区")
        else:
            signals.append("RSI 处于中性区间")

    if not rolling_window.empty:
        if latest["close"] >= rolling_window["high"].max():
            signals.append("收盘价接近或创出 20 日新高")
        elif latest["close"] <= rolling_window["low"].min():
            signals.append("收盘价接近或创出 20 日新低")

    return signals[:5]


def summarize_latest(bars: pd.DataFrame) -> dict[str, Any]:
    enriched = add_indicators(bars)
    if enriched.empty:
        return {}

    latest = enriched.iloc[-1]
    previous = enriched.iloc[-2] if len(enriched) > 1 else None
    previous_close = previous["close"] if previous is not None else None

    daily_change_pct = None
    if previous_close not in (None, 0) and pd.notna(previous_close):
        daily_change_pct = round((latest["close"] / previous_close - 1) * 100, 2)

    ma20 = latest.get("ma20")
    rsi14 = latest.get("rsi14")
    macd = latest.get("macd")
    macd_signal = latest.get("macd_signal")

    if pd.notna(rsi14):
        if rsi14 >= 70:
            rsi_state = "偏热"
        elif rsi14 <= 30:
            rsi_state = "偏冷"
        else:
            rsi_state = "中性"
    else:
        rsi_state = "数据不足"

    if pd.notna(macd) and pd.notna(macd_signal):
        macd_bias = "多头" if macd >= macd_signal else "空头"
    else:
        macd_bias = "数据不足"

    return {
        "trade_date": latest["trade_date"].strftime("%Y-%m-%d"),
        "close": round(float(latest["close"]), 2),
        "daily_change_pct": daily_change_pct,
        "ma5": _maybe_round(latest.get("ma5")),
        "ma10": _maybe_round(latest.get("ma10")),
        "ma20": _maybe_round(ma20),
        "ma60": _maybe_round(latest.get("ma60")),
        "volume": _maybe_round(latest.get("volume")),
        "amount": _maybe_round(latest.get("amount")),
        "rsi14": _maybe_round(rsi14),
        "rsi_state": rsi_state,
        "macd_bias": macd_bias,
        "is_above_ma20": bool(pd.notna(ma20) and latest["close"] >= ma20),
        "signals": build_signal_summary(enriched),
    }


def to_chart_payload(bars: pd.DataFrame) -> dict[str, list[Any]]:
    enriched = add_indicators(bars)
    if enriched.empty:
        return {
            "dates": [],
            "candles": [],
            "volume": [],
            "ma5": [],
            "ma10": [],
            "ma20": [],
            "ma60": [],
            "macd": [],
            "macd_signal": [],
            "macd_hist": [],
            "rsi14": [],
        }

    return {
        "dates": enriched["trade_date"].dt.strftime("%Y-%m-%d").tolist(),
        "candles": [
            [
                _maybe_round(row.open),
                _maybe_round(row.close),
                _maybe_round(row.low),
                _maybe_round(row.high),
            ]
            for row in enriched.itertuples(index=False)
        ],
        "volume": [_maybe_round(value) for value in enriched["volume"]],
        "ma5": [_maybe_round(value) for value in enriched["ma5"]],
        "ma10": [_maybe_round(value) for value in enriched["ma10"]],
        "ma20": [_maybe_round(value) for value in enriched["ma20"]],
        "ma60": [_maybe_round(value) for value in enriched["ma60"]],
        "macd": [_maybe_round(value) for value in enriched["macd"]],
        "macd_signal": [_maybe_round(value) for value in enriched["macd_signal"]],
        "macd_hist": [_maybe_round(value) for value in enriched["macd_hist"]],
        "rsi14": [_maybe_round(value) for value in enriched["rsi14"]],
    }


def _maybe_round(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), 2)
