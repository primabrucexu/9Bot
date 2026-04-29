from __future__ import annotations

from dataclasses import replace
import logging

from fastapi.testclient import TestClient
import pandas as pd

from app import db
from app.main import create_app
from app.services import jygs_diagram, market_data, report_generator, stock_screener


def _seed_stock_with_bars(settings, sample_bars: pd.DataFrame, *, symbol: str = "600519", name: str = "贵州茅台") -> None:
    db.init_db(settings.database_path)
    db.add_watchlist_item(settings.database_path, symbol, name)
    db.upsert_daily_bars(settings.database_path, symbol, sample_bars)


def _seed_universe_stock_with_bars(
    settings,
    sample_bars: pd.DataFrame,
    *,
    symbol: str = "600519",
    name: str = "贵州茅台",
    market: str = "SSE",
    board: str = "main",
) -> None:
    db.init_db(settings.database_path)
    db.upsert_stock_universe(
        settings.database_path,
        [
            {
                "symbol": symbol,
                "name": name,
                "market": market,
                "board": board,
                "is_st": False,
                "is_active": True,
            }
        ],
    )
    db.upsert_daily_bars(settings.database_path, symbol, sample_bars)


def _mock_spot_snapshot() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"代码": "600519", "名称": "贵州茅台"},
            {"代码": "000001", "名称": "平安银行"},
            {"代码": "002594", "名称": "比亚迪"},
            {"代码": "300750", "名称": "宁德时代"},
            {"代码": "688981", "名称": "中芯国际"},
            {"代码": "600001", "名称": "ST样本"},
            {"代码": "600002", "名称": "*ST样本"},
            {"代码": "830001", "名称": "北交样本"},
            {"代码": "900901", "名称": "B股样本"},
        ]
    )


def _mock_market_overview() -> list[dict[str, object]]:
    return [
        {
            "symbol": "sh000001",
            "name": "上证指数",
            "summary": {
                "trade_date": "2026-04-25",
                "close": 3288.41,
                "daily_change_pct": 0.82,
                "ma5": 3268.11,
                "ma10": 3244.56,
                "ma20": 3208.34,
                "ma60": 3138.92,
                "volume": 60503179800.0,
                "amount": None,
                "rsi14": 58.2,
                "rsi_state": "中性",
                "macd_bias": "多头",
                "is_above_ma20": True,
                "signals": ["收盘价位于 MA20 上方", "MACD 保持多头结构"],
            },
        },
        {
            "symbol": "sz399001",
            "name": "深证成指",
            "summary": {
                "trade_date": "2026-04-25",
                "close": 10456.32,
                "daily_change_pct": -0.36,
                "ma5": 10502.18,
                "ma10": 10524.41,
                "ma20": 10488.66,
                "ma60": 10196.75,
                "volume": 70972943878.0,
                "amount": None,
                "rsi14": 47.5,
                "rsi_state": "中性",
                "macd_bias": "空头",
                "is_above_ma20": False,
                "signals": ["收盘价位于 MA20 下方", "MACD 保持空头结构"],
            },
        },
        {
            "symbol": "sz399006",
            "name": "创业板指",
            "summary": {
                "trade_date": "2026-04-25",
                "close": 2104.78,
                "daily_change_pct": 1.14,
                "ma5": 2081.55,
                "ma10": 2068.72,
                "ma20": 2044.9,
                "ma60": 1988.43,
                "volume": 22796018188.0,
                "amount": None,
                "rsi14": 60.1,
                "rsi_state": "中性",
                "macd_bias": "多头",
                "is_above_ma20": True,
                "signals": ["收盘价位于 MA20 上方", "MACD 保持多头结构"],
            },
        },
    ]


def _mock_jygs_status(*, latest: dict[str, object] | None = None, login_ready: bool = True) -> dict[str, object]:
    return {
        "login_ready": login_ready,
        "storage_state_path": "D:/tmp/jygs/auth/storage-state.json",
        "login_flow": {
            "status": "saved" if login_ready else "idle",
            "message": "登录态已保存。" if login_ready else None,
            "login_url": "https://www.jiuyangongshe.com/action/2026-04-29" if login_ready else None,
            "updated_at": "2026-04-29T09:00:00+00:00",
        },
        "latest": latest,
    }


def test_watchlist_returns_empty_state(settings_factory):
    app = create_app(settings_factory())

    with TestClient(app) as client:
        response = client.get("/api/watchlist")

    assert response.status_code == 200
    assert response.json() == {"rows": []}


def test_watchlist_returns_rows(settings_factory, sample_bars):
    settings = settings_factory()
    _seed_stock_with_bars(settings, sample_bars)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/api/watchlist")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["symbol"] == "600519"
    assert payload["rows"][0]["name"] == "贵州茅台"
    assert payload["rows"][0]["has_data"] is True
    assert payload["rows"][0]["last_close"] is not None
    assert payload["rows"][0]["last_trade_date"] is not None


def test_base_stock_pool_filters_main_board_non_st(settings_factory, monkeypatch):
    app = create_app(settings_factory())
    monkeypatch.setattr(market_data.ak, "stock_zh_a_spot_em", _mock_spot_snapshot)

    with TestClient(app) as client:
        response = client.get("/api/stock-pool/base")

    assert response.status_code == 200
    assert response.json() == {
        "rows": [
            {"symbol": "000001", "name": "平安银行"},
            {"symbol": "002594", "name": "比亚迪"},
            {"symbol": "600519", "name": "贵州茅台"},
        ],
        "total": 3,
        "offset": 0,
        "limit": 50,
    }


def test_base_stock_pool_supports_search_and_pagination(settings_factory, monkeypatch):
    app = create_app(settings_factory())
    monkeypatch.setattr(market_data.ak, "stock_zh_a_spot_em", _mock_spot_snapshot)

    with TestClient(app) as client:
        search_response = client.get("/api/stock-pool/base", params={"q": "平安", "limit": 5, "offset": 0})
        page_response = client.get("/api/stock-pool/base", params={"limit": 1, "offset": 1})

    assert search_response.status_code == 200
    assert search_response.json() == {
        "rows": [{"symbol": "000001", "name": "平安银行"}],
        "total": 1,
        "offset": 0,
        "limit": 5,
    }
    assert page_response.status_code == 200
    assert page_response.json() == {
        "rows": [{"symbol": "002594", "name": "比亚迪"}],
        "total": 3,
        "offset": 1,
        "limit": 1,
    }


def test_limit_up_copy_returns_ranked_candidates(settings_factory, monkeypatch):
    app = create_app(settings_factory())

    monkeypatch.setattr(
        stock_screener,
        "screen_limit_up_copy",
        lambda settings, limit=10: {
            "trade_date": "2026-04-27",
            "rows": [
                {
                    "symbol": "600111",
                    "name": "国电样本",
                    "sector": "电力",
                    "score": 88,
                    "trade_date": "2026-04-27",
                    "last_close": 31.0,
                    "last_limit_up_date": "2026-04-24",
                    "limit_up_count_7d": 2,
                    "max_board_count": 2,
                    "daily_change_pct": 3.0,
                    "ma_status": "MA20 上方",
                    "macd_bias": "多头",
                    "rsi_state": "中性",
                    "signals": ["热点板块第 1 名：电力", "近 7 个交易日涨停 2 次"],
                }
            ],
            "total": 1,
            "limit": limit,
            "hot_sectors": [{"name": "电力", "count": 8, "rank": 1}],
        },
    )

    with TestClient(app) as client:
        response = client.get("/api/stock-pool/limit-up-copy", params={"limit": 5})

    assert response.status_code == 200
    assert response.json() == {
        "trade_date": "2026-04-27",
        "rows": [
            {
                "symbol": "600111",
                "name": "国电样本",
                "sector": "电力",
                "score": 88,
                "trade_date": "2026-04-27",
                "last_close": 31.0,
                "last_limit_up_date": "2026-04-24",
                "limit_up_count_7d": 2,
                "max_board_count": 2,
                "daily_change_pct": 3.0,
                "ma_status": "MA20 上方",
                "macd_bias": "多头",
                "rsi_state": "中性",
                "signals": ["热点板块第 1 名：电力", "近 7 个交易日涨停 2 次"],
            }
        ],
        "total": 1,
        "limit": 5,
        "hot_sectors": [{"name": "电力", "count": 8, "rank": 1}],
    }


def test_limit_up_copy_returns_400_when_screen_failed(settings_factory, monkeypatch):
    app = create_app(settings_factory())

    def fake_screen_limit_up_copy(settings, limit=10):
        raise stock_screener.StockScreenerError("选股失败")

    monkeypatch.setattr(stock_screener, "screen_limit_up_copy", fake_screen_limit_up_copy)

    with TestClient(app) as client:
        response = client.get("/api/stock-pool/limit-up-copy")

    assert response.status_code == 400
    assert response.json()["detail"] == "选股失败"


def test_market_overview_returns_index_summaries(settings_factory, monkeypatch):
    app = create_app(settings_factory())
    monkeypatch.setattr(market_data, "build_market_overview", lambda settings: _mock_market_overview())

    with TestClient(app) as client:
        response = client.get("/api/market-overview")

    assert response.status_code == 200
    payload = response.json()
    assert [item["name"] for item in payload["indices"]] == ["上证指数", "深证成指", "创业板指"]
    assert payload["indices"][0]["summary"]["trade_date"] == "2026-04-25"
    assert payload["indices"][0]["summary"]["macd_bias"] == "多头"


def test_market_overview_returns_400_when_fetch_failed(settings_factory, monkeypatch):
    app = create_app(settings_factory())

    def fake_build_market_overview(settings):
        raise market_data.MarketDataError("获取指数失败")

    monkeypatch.setattr(market_data, "build_market_overview", fake_build_market_overview)

    with TestClient(app) as client:
        response = client.get("/api/market-overview")

    assert response.status_code == 400
    assert response.json()["detail"] == "获取指数失败"


def test_market_universe_refresh_returns_count(settings_factory, monkeypatch):
    app = create_app(settings_factory())
    monkeypatch.setattr(
        market_data,
        "refresh_stock_universe",
        lambda settings: {"scope": "full-a-share", "count": 5120},
    )

    with TestClient(app) as client:
        response = client.post("/api/market-data/universe/refresh")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "scope": "full-a-share", "count": 5120}


def test_market_data_sync_uses_default_one_month_window(settings_factory, monkeypatch):
    app = create_app(settings_factory())
    calls: list[tuple[int, bool]] = []

    def fake_sync_universe_daily_bars(settings, *, history_days=30, symbols=None, refresh_universe=False):
        calls.append((history_days, refresh_universe))
        return {
            "scope": "full-a-share",
            "history_days": history_days,
            "universe_count": 5120,
            "synced_count": 5120,
            "last_trade_date": "2026-04-29",
        }

    monkeypatch.setattr(market_data, "sync_universe_daily_bars", fake_sync_universe_daily_bars)

    with TestClient(app) as client:
        response = client.post("/api/market-data/sync")

    assert response.status_code == 200
    assert calls == [(30, False)]
    assert response.json() == {
        "ok": True,
        "scope": "full-a-share",
        "history_days": 30,
        "universe_count": 5120,
        "synced_count": 5120,
        "last_trade_date": "2026-04-29",
    }


def test_market_data_sync_accepts_custom_history_window(settings_factory, monkeypatch):
    app = create_app(settings_factory())

    def fake_sync_universe_daily_bars(settings, *, history_days=30, symbols=None, refresh_universe=False):
        assert history_days == 365
        assert refresh_universe is True
        return {
            "scope": "full-a-share",
            "history_days": 365,
            "universe_count": 5120,
            "synced_count": 5120,
            "last_trade_date": "2026-04-29",
        }

    monkeypatch.setattr(market_data, "sync_universe_daily_bars", fake_sync_universe_daily_bars)

    with TestClient(app) as client:
        response = client.post(
            "/api/market-data/sync",
            json={"history_days": 365, "refresh_universe": True},
        )

    assert response.status_code == 200
    assert response.json()["history_days"] == 365
    assert response.json()["synced_count"] == 5120


def test_jygs_status_returns_latest_diagram(settings_factory, monkeypatch):
    app = create_app(settings_factory())
    monkeypatch.setattr(
        jygs_diagram,
        "get_status",
        lambda settings: _mock_jygs_status(
            latest={
                "date": "2026-04-28",
                "status": "downloaded",
                "output_path": "D:/tmp/jygs/diagrams/2026-04-28.png",
                "source_image_url": "https://cdn.example.com/2026-04-28.png",
                "updated_at": "2026-04-29T09:30:00+00:00",
            }
        ),
    )

    with TestClient(app) as client:
        response = client.get("/api/jygs/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["login_ready"] is True
    assert payload["latest"]["date"] == "2026-04-28"
    assert payload["latest"]["image_url"].endswith("/api/jygs/diagram/image/2026-04-28")
    assert payload["latest"]["source_image_url"] == "https://cdn.example.com/2026-04-28.png"


def test_jygs_login_start_returns_status(settings_factory, monkeypatch):
    app = create_app(settings_factory())
    monkeypatch.setattr(
        jygs_diagram,
        "start_login",
        lambda settings: {
            **_mock_jygs_status(login_ready=False),
            "login_flow": {
                "status": "waiting",
                "message": "请在打开的 Edge 窗口中完成登录。",
                "login_url": "https://www.jiuyangongshe.com/action/2026-04-29",
                "updated_at": "2026-04-29T09:10:00+00:00",
            },
        },
    )

    with TestClient(app) as client:
        response = client.post("/api/jygs/login/start")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["status"]["login_flow"]["status"] == "waiting"


def test_jygs_login_complete_returns_400_when_flow_failed(settings_factory, monkeypatch):
    app = create_app(settings_factory())

    def fake_complete_login(settings):
        raise jygs_diagram.JiuyangongsheDiagramError("登录窗口已关闭，请重新开始。")

    monkeypatch.setattr(jygs_diagram, "complete_login", fake_complete_login)

    with TestClient(app) as client:
        response = client.post("/api/jygs/login/complete")

    assert response.status_code == 400
    assert response.json()["detail"] == "登录窗口已关闭，请重新开始。"


def test_jygs_diagram_fetch_returns_refreshed_status(settings_factory, monkeypatch):
    app = create_app(settings_factory())
    monkeypatch.setattr(
        jygs_diagram,
        "fetch_diagrams",
        lambda settings, latest=True, force=False: {
            "requested_dates": ["2026-04-28"],
            "fetched": [
                {
                    "date": "2026-04-28",
                    "outputPath": "D:/tmp/jygs/diagrams/2026-04-28.png",
                    "imageUrl": "https://cdn.example.com/2026-04-28.png",
                    "status": "downloaded",
                }
            ],
            "skipped": [],
            "state_path": "D:/tmp/jygs/state.json",
        },
    )
    monkeypatch.setattr(
        jygs_diagram,
        "get_status",
        lambda settings: _mock_jygs_status(
            latest={
                "date": "2026-04-28",
                "status": "downloaded",
                "output_path": "D:/tmp/jygs/diagrams/2026-04-28.png",
                "source_image_url": "https://cdn.example.com/2026-04-28.png",
                "updated_at": "2026-04-29T09:30:00+00:00",
            }
        ),
    )

    with TestClient(app) as client:
        response = client.post("/api/jygs/diagram/fetch")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["requested_dates"] == ["2026-04-28"]
    assert payload["status"]["latest"]["date"] == "2026-04-28"


def test_jygs_diagram_image_returns_file_response(settings_factory, monkeypatch):
    settings = settings_factory()
    image_path = settings.data_dir / "2026-04-28.png"
    image_path.write_bytes(b"fake-image")
    app = create_app(settings)
    monkeypatch.setattr(jygs_diagram, "resolve_diagram_file", lambda settings, trade_date: image_path)

    with TestClient(app) as client:
        response = client.get("/api/jygs/diagram/image/2026-04-28")

    assert response.status_code == 200
    assert response.content == b"fake-image"


def test_add_watchlist_returns_400_for_invalid_symbol(settings_factory):
    app = create_app(settings_factory())

    with TestClient(app) as client:
        response = client.post("/api/watchlist", json={"symbol": "abc"})

    assert response.status_code == 400
    assert response.json()["detail"] == "股票代码格式不正确，请输入 6 位 A 股代码。"


def test_add_watchlist_returns_400_for_non_base_universe_symbol(settings_factory, monkeypatch):
    app = create_app(settings_factory())
    monkeypatch.setattr(market_data.ak, "stock_zh_a_spot_em", _mock_spot_snapshot)

    with TestClient(app) as client:
        response = client.post("/api/watchlist", json={"symbol": "300750"})

    assert response.status_code == 400
    assert response.json()["detail"] == "仅支持上证、深证范围内且名称不含 ST 的股票。"


def test_add_watchlist_returns_stock_when_symbol_is_in_base_universe(settings_factory, monkeypatch):
    settings = settings_factory()
    app = create_app(settings)
    monkeypatch.setattr(market_data.ak, "stock_zh_a_spot_em", _mock_spot_snapshot)

    with TestClient(app) as client:
        response = client.post("/api/watchlist", json={"symbol": "600519"})

    assert response.status_code == 200
    assert response.json() == {"ok": True, "symbol": "600519", "name": "贵州茅台"}
    assert db.get_watchlist_item(settings.database_path, "600519") is not None


def test_remove_watchlist_returns_400_when_symbol_missing(settings_factory):
    app = create_app(settings_factory())

    with TestClient(app) as client:
        response = client.delete("/api/watchlist/600519")

    assert response.status_code == 400
    assert response.json()["detail"] == "该股票不在自选股列表中。"


def test_sync_returns_400_and_logs_warning(settings_factory, monkeypatch, caplog):
    app = create_app(settings_factory())

    def fake_sync_watchlist_daily_bars(settings):
        raise market_data.MarketDataError("同步失败")

    monkeypatch.setattr(market_data, "sync_watchlist_daily_bars", fake_sync_watchlist_daily_bars)

    with caplog.at_level(logging.INFO):
        with TestClient(app) as client:
            response = client.post("/api/watchlist/sync")

    assert response.status_code == 400
    assert response.json()["detail"] == "同步失败"
    assert any(
        record.levelno == logging.WARNING
        and "Sync watchlist failed" in record.message
        and str(app.state.settings.database_path) in record.message
        for record in caplog.records
    )
    assert any(
        record.levelno == logging.INFO
        and "Sync watchlist requested" in record.message
        for record in caplog.records
    )


def test_stock_detail_returns_summary(settings_factory, sample_bars):
    settings = settings_factory()
    _seed_stock_with_bars(settings, sample_bars)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/api/stocks/600519")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stock"]["symbol"] == "600519"
    assert payload["stock"]["name"] == "贵州茅台"
    assert payload["has_data"] is True
    assert payload["summary"]["trade_date"]
    assert isinstance(payload["summary"]["signals"], list)


def test_stock_detail_returns_summary_from_stock_universe_without_watchlist(settings_factory, sample_bars):
    settings = settings_factory()
    _seed_universe_stock_with_bars(settings, sample_bars, symbol="300750", name="宁德时代", market="SZSE", board="chinext")
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/api/stocks/300750")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stock"]["symbol"] == "300750"
    assert payload["stock"]["name"] == "宁德时代"
    assert payload["stock"]["market"] == "SZSE"
    assert payload["stock"]["board"] == "chinext"
    assert payload["has_data"] is True


def test_stock_detail_returns_resolved_name_without_local_universe(settings_factory, monkeypatch):
    app = create_app(settings_factory())
    monkeypatch.setattr(market_data, "resolve_symbol_name", lambda symbol: "贵州茅台")

    with TestClient(app) as client:
        response = client.get("/api/stocks/600519")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stock"]["symbol"] == "600519"
    assert payload["stock"]["name"] == "贵州茅台"
    assert payload["has_data"] is False
    assert payload["summary"] is None



def test_stock_detail_returns_404_when_symbol_missing(settings_factory, monkeypatch):
    app = create_app(settings_factory())

    def raise_error(symbol: str):
        raise market_data.MarketDataError("missing")

    monkeypatch.setattr(market_data, "resolve_symbol_name", raise_error)

    with TestClient(app) as client:
        response = client.get("/api/stocks/600519")

    assert response.status_code == 404
    assert response.json()["detail"] == "未找到该股票。"


def test_chart_returns_404_and_logs_warning_when_data_missing(settings_factory, monkeypatch, caplog):
    settings = settings_factory()
    db.init_db(settings.database_path)
    db.add_watchlist_item(settings.database_path, "600519", "贵州茅台")
    app = create_app(settings)

    monkeypatch.setattr(db, "get_daily_bars", lambda *args, **kwargs: pd.DataFrame())

    with caplog.at_level(logging.INFO):
        with TestClient(app) as client:
            response = client.get("/api/stocks/600519/chart")

    assert response.status_code == 404
    assert response.json()["detail"] == "该股票还没有可用历史数据，请先同步日线数据。"
    assert any(
        record.levelno == logging.WARNING
        and "Chart data missing" in record.message
        and "600519" in record.message
        and str(app.state.settings.database_path) in record.message
        for record in caplog.records
    )
    assert any(
        record.levelno == logging.INFO
        and "Stock chart requested" in record.message
        and "600519" in record.message
        for record in caplog.records
    )


def test_latest_report_returns_404_when_missing(settings_factory):
    app = create_app(settings_factory())

    with TestClient(app) as client:
        response = client.get("/api/reports/latest")

    assert response.status_code == 404
    assert response.json()["detail"] == "还没有可用日报。"


def test_get_report_by_date_returns_saved_report(settings_factory):
    settings = settings_factory()
    db.init_db(settings.database_path)
    db.save_daily_report(
        settings.database_path,
        report_date="2026-04-24",
        report_markdown="# 今日市场观察日报\n测试内容",
        context_json="{}",
        model_name="claude-opus-4-6",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/api/reports/2026-04-24")

    assert response.status_code == 200
    assert response.json()["report_date"] == "2026-04-24"
    assert response.json()["report_markdown"] == "# 今日市场观察日报\n测试内容"


def test_generate_report_returns_report_date(settings_factory, monkeypatch):
    app = create_app(settings_factory(anthropic_api_key="test-key"))

    def fake_generate_daily_report(settings):
        return {
            "report_date": "2026-04-24",
            "report_markdown": "# 今日市场观察日报",
            "model_name": "claude-opus-4-6",
            "created_at": "2026-04-24T10:00:00+00:00",
        }

    monkeypatch.setattr(report_generator, "generate_daily_report", fake_generate_daily_report)

    with TestClient(app) as client:
        response = client.post("/api/reports")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "report_date": "2026-04-24"}


def test_cors_allows_configured_frontend_origin(settings_factory):
    settings = replace(settings_factory(), cors_allowed_origins=("http://127.0.0.1:5173",))
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.options(
            "/api/watchlist",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
