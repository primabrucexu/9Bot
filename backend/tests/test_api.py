from __future__ import annotations

from dataclasses import replace
import logging

from fastapi.testclient import TestClient
import pandas as pd

from app import db
from app.main import create_app
from app.services import market_data, report_generator


def _seed_stock_with_bars(settings, sample_bars: pd.DataFrame, *, symbol: str = "600519", name: str = "贵州茅台") -> None:
    db.init_db(settings.database_path)
    db.add_watchlist_item(settings.database_path, symbol, name)
    db.upsert_daily_bars(settings.database_path, symbol, sample_bars)


def test_dashboard_returns_empty_state(settings_factory):
    app = create_app(settings_factory())

    with TestClient(app) as client:
        response = client.get("/api/dashboard")

    assert response.status_code == 200
    assert response.json() == {"rows": [], "latest_report": None}


def test_dashboard_returns_rows_and_latest_report(settings_factory, sample_bars):
    settings = settings_factory()
    _seed_stock_with_bars(settings, sample_bars)
    db.save_daily_report(
        settings.database_path,
        report_date="2026-04-24",
        report_markdown="# 今日自选股日报\n" + "内容" * 300,
        context_json="{}",
        model_name="claude-opus-4-6",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/api/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["symbol"] == "600519"
    assert payload["rows"][0]["name"] == "贵州茅台"
    assert payload["rows"][0]["has_data"] is True
    assert payload["latest_report"]["report_date"] == "2026-04-24"
    assert payload["latest_report"]["preview_markdown"].startswith("# 今日自选股日报")
    assert payload["latest_report"]["preview_markdown"].endswith("...")


def test_add_watchlist_returns_400_for_invalid_symbol(settings_factory):
    app = create_app(settings_factory())

    with TestClient(app) as client:
        response = client.post("/api/watchlist", json={"symbol": "abc"})

    assert response.status_code == 400
    assert response.json()["detail"] == "股票代码格式不正确，请输入 6 位 A 股代码。"


def test_remove_watchlist_returns_400_when_symbol_missing(settings_factory):
    app = create_app(settings_factory())

    with TestClient(app) as client:
        response = client.delete("/api/watchlist/600519")

    assert response.status_code == 400
    assert response.json()["detail"] == "该股票不在自选股列表中。"


def test_refresh_returns_400_and_logs_warning(settings_factory, monkeypatch, caplog):
    app = create_app(settings_factory())

    def fake_refresh_watchlist(settings):
        raise market_data.MarketDataError("刷新失败")

    monkeypatch.setattr(market_data, "refresh_watchlist", fake_refresh_watchlist)

    with caplog.at_level(logging.INFO):
        with TestClient(app) as client:
            response = client.post("/api/watchlist/refresh")

    assert response.status_code == 400
    assert response.json()["detail"] == "刷新失败"
    assert any(
        record.levelno == logging.WARNING
        and "Refresh watchlist failed" in record.message
        and str(app.state.settings.database_path) in record.message
        for record in caplog.records
    )
    assert any(
        record.levelno == logging.INFO
        and "Refresh watchlist requested" in record.message
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


def test_stock_detail_returns_404_when_symbol_missing(settings_factory):
    app = create_app(settings_factory())

    with TestClient(app) as client:
        response = client.get("/api/stocks/600519")

    assert response.status_code == 404
    assert response.json()["detail"] == "未找到该自选股。"


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
    assert response.json()["detail"] == "该股票还没有可用历史数据，请先刷新行情。"
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
        report_markdown="# 今日自选股日报\n测试内容",
        context_json="{}",
        model_name="claude-opus-4-6",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/api/reports/2026-04-24")

    assert response.status_code == 200
    assert response.json()["report_date"] == "2026-04-24"
    assert response.json()["report_markdown"] == "# 今日自选股日报\n测试内容"


def test_generate_report_returns_report_date(settings_factory, monkeypatch):
    app = create_app(settings_factory(anthropic_api_key="test-key"))

    def fake_generate_daily_report(settings):
        return {
            "report_date": "2026-04-24",
            "report_markdown": "# 今日自选股日报",
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
            "/api/dashboard",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
