from __future__ import annotations

import pandas as pd

from app import db
from app.services import market_data


def _mock_full_market_snapshot() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"代码": "600519", "名称": "贵州茅台"},
            {"代码": "300750", "名称": "宁德时代"},
            {"代码": "688981", "名称": "中芯国际"},
            {"代码": "830001", "名称": "北交样本"},
            {"代码": "900901", "名称": "B股样本"},
            {"代码": "600001", "名称": "ST样本"},
        ]
    )


def test_refresh_stock_universe_persists_full_a_share_metadata(settings_factory, monkeypatch):
    settings = settings_factory()
    db.init_db(settings.database_path)
    monkeypatch.setattr(market_data.ak, "stock_zh_a_spot_em", _mock_full_market_snapshot)

    payload = market_data.refresh_stock_universe(settings)
    rows = db.list_stock_universe(settings.database_path, active_only=False)

    assert payload == {"scope": "full-a-share", "count": 5}
    assert [row["symbol"] for row in rows] == ["300750", "600001", "600519", "688981", "830001"]
    assert rows[0]["market"] == "SZSE"
    assert rows[0]["board"] == "chinext"
    assert rows[1]["is_st"] is True
    assert rows[-1]["market"] == "BSE"
    assert rows[-1]["board"] == "beijing"


def test_sync_universe_daily_bars_uses_requested_history_window(settings_factory, sample_bars, monkeypatch):
    settings = settings_factory()
    db.init_db(settings.database_path)
    db.upsert_stock_universe(
        settings.database_path,
        [
            {
                "symbol": "000001",
                "name": "平安银行",
                "market": "SZSE",
                "board": "main",
                "is_st": False,
                "is_active": True,
            },
            {
                "symbol": "600519",
                "name": "贵州茅台",
                "market": "SSE",
                "board": "main",
                "is_st": False,
                "is_active": True,
            },
        ],
    )

    calls: list[tuple[str, int]] = []

    def fake_fetch_history(symbol: str, history_days: int) -> pd.DataFrame:
        calls.append((symbol, history_days))
        return sample_bars.tail(20).reset_index(drop=True)

    monkeypatch.setattr(market_data, "_fetch_history", fake_fetch_history)

    payload = market_data.sync_universe_daily_bars(settings, history_days=365)
    sync_state = db.get_market_sync_state(settings.database_path, "full-a-share")

    assert payload["scope"] == "full-a-share"
    assert payload["history_days"] == 365
    assert payload["universe_count"] == 2
    assert payload["synced_count"] == 2
    assert calls == [("000001", 365), ("600519", 365)]
    assert sync_state is not None
    assert sync_state["status"] == "succeeded"
    assert sync_state["last_trade_date"] == sample_bars.iloc[-1]["trade_date"].strftime("%Y-%m-%d")
    assert len(db.get_daily_bars(settings.database_path, "000001")) == 20
    assert len(db.get_daily_bars(settings.database_path, "600519")) == 20


def test_sync_universe_daily_bars_rejects_out_of_range_window(settings_factory):
    settings = settings_factory()
    db.init_db(settings.database_path)

    try:
        market_data.sync_universe_daily_bars(settings, history_days=3651)
    except market_data.MarketDataError as exc:
        assert str(exc) == "history_days 不能超过 3650 天。"
    else:  # pragma: no cover
        raise AssertionError("expected MarketDataError")
