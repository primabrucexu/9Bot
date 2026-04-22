from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_dashboard_renders_empty_state(settings_factory):
    app = create_app(settings_factory())

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "还没有自选股" in response.text
    assert "本地 A 股分析工作台" in response.text
