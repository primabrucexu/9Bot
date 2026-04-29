from __future__ import annotations

from datetime import date

import pandas as pd

from app.services import stock_screener


TRADE_DATES = [
    date(2026, 4, 14),
    date(2026, 4, 15),
    date(2026, 4, 16),
    date(2026, 4, 17),
    date(2026, 4, 20),
    date(2026, 4, 21),
    date(2026, 4, 22),
    date(2026, 4, 23),
    date(2026, 4, 24),
    date(2026, 4, 27),
]


def _mock_trade_calendar() -> pd.DataFrame:
    return pd.DataFrame({"trade_date": TRADE_DATES})


def _mock_spot_snapshot() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"代码": "600111", "名称": "国电样本"},
            {"代码": "000001", "名称": "平安银行"},
            {"代码": "300001", "名称": "创业样本"},
            {"代码": "600222", "名称": "ST样本"},
        ]
    )


def _mock_limit_up_pool(date: str) -> pd.DataFrame:
    rows_by_date = {
        "20260421": [
            {"代码": "600111", "名称": "国电样本", "所属行业": "电力", "连板数": 1, "涨停统计": "1/1"},
            {"代码": "300001", "名称": "创业样本", "所属行业": "电力", "连板数": 1, "涨停统计": "1/1"},
        ],
        "20260422": [
            {"代码": "000001", "名称": "平安银行", "所属行业": "电力", "连板数": 1, "涨停统计": "1/1"},
        ],
        "20260423": [
            {"代码": "600333", "名称": "机器人样本", "所属行业": "机器人", "连板数": 1, "涨停统计": "1/1"},
        ],
        "20260424": [
            {"代码": "600111", "名称": "国电样本", "所属行业": "电力", "连板数": 2, "涨停统计": "2/2"},
            {"代码": "000001", "名称": "平安银行", "所属行业": "电力", "连板数": 1, "涨停统计": "1/1"},
            {"代码": "600222", "名称": "ST样本", "所属行业": "电力", "连板数": 1, "涨停统计": "1/1"},
        ],
        "20260427": [
            {"代码": "600333", "名称": "机器人样本", "所属行业": "机器人", "连板数": 2, "涨停统计": "2/2"},
        ],
    }
    return pd.DataFrame(rows_by_date.get(date, []))


def _build_history(symbol: str, history_days: int) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=83, freq="B")
    close = pd.Series([20 + index * 0.1 for index in range(len(dates))], dtype="float64")
    open_price = close - 0.2
    high = close + 0.6
    low = close - 0.5
    volume = pd.Series([1_200_000 + index * 3_000 for index in range(len(dates))], dtype="float64")
    amount = close * volume * 10

    frame = pd.DataFrame(
        {
            "trade_date": dates,
            "open": open_price,
            "close": close,
            "high": high,
            "low": low,
            "volume": volume,
            "amount": amount,
        }
    )

    if symbol == "600111":
        overrides = {
            "2026-04-21": {"open": 27.6, "close": 30.4, "high": 30.4, "low": 27.5, "volume": 3_200_000},
            "2026-04-22": {"open": 29.9, "close": 29.5, "high": 30.0, "low": 29.0, "volume": 1_500_000},
            "2026-04-23": {"open": 29.4, "close": 29.2, "high": 29.6, "low": 28.8, "volume": 1_300_000},
            "2026-04-24": {"open": 29.4, "close": 32.1, "high": 32.1, "low": 29.2, "volume": 3_600_000},
            "2026-04-27": {"open": 30.3, "close": 31.4, "high": 31.7, "low": 30.1, "volume": 2_300_000},
        }
    else:
        overrides = {
            "2026-04-22": {"open": 24.6, "close": 27.0, "high": 27.0, "low": 24.5, "volume": 2_900_000},
            "2026-04-23": {"open": 26.8, "close": 26.7, "high": 26.9, "low": 26.3, "volume": 2_200_000},
            "2026-04-24": {"open": 26.5, "close": 27.0, "high": 27.1, "low": 26.4, "volume": 2_000_000},
            "2026-04-27": {"open": 26.9, "close": 27.1, "high": 27.3, "low": 26.8, "volume": 2_050_000},
        }

    for trade_date, values in overrides.items():
        mask = frame["trade_date"] == pd.Timestamp(trade_date)
        for column, value in values.items():
            frame.loc[mask, column] = value
        frame.loc[mask, "amount"] = frame.loc[mask, "close"] * frame.loc[mask, "volume"] * 10

    return frame


def test_screen_limit_up_copy_returns_ranked_main_board_non_st_candidates(settings_factory, monkeypatch):
    settings = settings_factory()

    monkeypatch.setattr(stock_screener.ak, "tool_trade_date_hist_sina", _mock_trade_calendar)
    monkeypatch.setattr(stock_screener.ak, "stock_zt_pool_em", _mock_limit_up_pool)
    monkeypatch.setattr(stock_screener.market_data.ak, "stock_zh_a_spot_em", _mock_spot_snapshot)
    monkeypatch.setattr(stock_screener.market_data, "_fetch_history", _build_history)

    payload = stock_screener.screen_limit_up_copy(settings, limit=10)

    assert payload["trade_date"] == "2026-04-27"
    assert payload["hot_sectors"][0] == {"name": "电力", "count": 4, "rank": 1}
    assert [row["symbol"] for row in payload["rows"]] == ["600111", "000001"]
    assert payload["rows"][0]["score"] > payload["rows"][1]["score"]
    assert all(not row["name"].upper().startswith("ST") for row in payload["rows"])
    assert all(row["symbol"] != "300001" for row in payload["rows"])
    assert payload["rows"][0]["sector"] == "电力"
    assert payload["rows"][0]["last_limit_up_date"] == "2026-04-24"
