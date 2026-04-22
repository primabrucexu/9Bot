from __future__ import annotations

import pandas as pd

from app.services import indicators


def test_add_indicators_populates_core_columns(sample_bars):
    enriched = indicators.add_indicators(sample_bars)

    assert {"ma5", "ma10", "ma20", "ma60", "macd", "macd_signal", "macd_hist", "rsi14"}.issubset(
        enriched.columns
    )
    assert pd.notna(enriched.iloc[-1]["ma20"])
    assert pd.notna(enriched.iloc[-1]["macd"])


def test_summary_and_chart_payload_are_usable(sample_bars):
    summary = indicators.summarize_latest(sample_bars)
    payload = indicators.to_chart_payload(sample_bars.tail(60))

    assert summary["trade_date"] == "2024-03-30"
    assert isinstance(summary["signals"], list)
    assert len(summary["signals"]) >= 1

    assert len(payload["dates"]) == 60
    assert len(payload["candles"]) == 60
    assert len(payload["candles"][0]) == 4
    assert len(payload["macd_hist"]) == 60
