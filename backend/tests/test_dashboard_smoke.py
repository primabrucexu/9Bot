from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_dashboard_api_smoke_returns_empty_payload(settings_factory):
    app = create_app(settings_factory())

    with TestClient(app) as client:
        response = client.get("/api/dashboard")

    assert response.status_code == 200
    assert response.json() == {"rows": [], "latest_report": None}
