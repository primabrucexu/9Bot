from __future__ import annotations

import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_relative_paths_resolve_from_project_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NINEBOT_DATA_DIR", "custom-data")
    monkeypatch.setenv("NINEBOT_DB_PATH", "custom-db/9bot.db")

    settings = get_settings()

    assert settings.data_dir == settings.project_root / "custom-data"
    assert settings.database_path == settings.project_root / "custom-db" / "9bot.db"
    assert settings.data_dir != tmp_path / "custom-data"
    assert settings.database_path != tmp_path / "custom-db" / "9bot.db"


def test_database_path_defaults_under_resolved_data_dir(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NINEBOT_DATA_DIR", "custom-data")
    monkeypatch.setenv("NINEBOT_DB_PATH", "")

    settings = get_settings()

    assert settings.data_dir == settings.project_root / "custom-data"
    assert settings.database_path == settings.project_root / "custom-data" / "9bot.db"


def test_log_level_defaults_to_info(monkeypatch):
    monkeypatch.setenv("NINEBOT_LOG_LEVEL", "")

    settings = get_settings()

    assert settings.log_level == "INFO"


def test_log_level_can_be_configured(monkeypatch):
    monkeypatch.setenv("NINEBOT_LOG_LEVEL", "debug")

    settings = get_settings()

    assert settings.log_level == "DEBUG"


def test_cors_origins_are_parsed_and_normalized(monkeypatch):
    monkeypatch.setenv(
        "NINEBOT_CORS_ORIGINS",
        "http://127.0.0.1:5173/ , http://localhost:5173",
    )

    settings = get_settings()

    assert settings.cors_allowed_origins == (
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    )


def test_frontend_dist_dir_resolves_from_project_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NINEBOT_FRONTEND_DIST", "../frontend/dist")

    settings = get_settings()

    assert settings.frontend_dist_dir == settings.project_root.parent / "frontend" / "dist"
    assert settings.frontend_dist_dir != tmp_path / "frontend" / "dist"
