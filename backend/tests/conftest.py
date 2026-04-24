from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.config import Settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings_factory(tmp_path):
    def _factory(*, anthropic_api_key: str | None = None) -> Settings:
        return Settings(
            project_root=PROJECT_ROOT,
            data_dir=tmp_path,
            database_path=tmp_path / "9bot.db",
            static_dir=PROJECT_ROOT / "app" / "static",
            templates_dir=PROJECT_ROOT / "app" / "templates",
            anthropic_api_key=anthropic_api_key,
            anthropic_model="claude-opus-4-6",
            report_max_tokens=16000,
            history_days=365,
            log_level="INFO",
        )

    return _factory


@pytest.fixture
def sample_bars() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=90, freq="D")
    base = pd.Series(range(90), dtype="float64") * 0.45 + 20
    return pd.DataFrame(
        {
            "trade_date": dates,
            "open": base + 0.2,
            "high": base + 0.8,
            "low": base - 0.5,
            "close": base + 0.4,
            "volume": 1_000_000 + pd.Series(range(90)) * 8_000,
            "amount": 100_000_000 + pd.Series(range(90)) * 1_200_000,
        }
    )
