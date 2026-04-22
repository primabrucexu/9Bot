from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    database_path: Path
    static_dir: Path
    templates_dir: Path
    anthropic_api_key: str | None
    anthropic_model: str
    report_max_tokens: int
    history_days: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")

    data_dir = Path(os.getenv("NINEBOT_DATA_DIR", str(project_root / "data")))
    database_path = Path(os.getenv("NINEBOT_DB_PATH", str(data_dir / "9bot.db")))

    return Settings(
        project_root=project_root,
        data_dir=data_dir,
        database_path=database_path,
        static_dir=project_root / "app" / "static",
        templates_dir=project_root / "app" / "templates",
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6"),
        report_max_tokens=int(os.getenv("ANTHROPIC_MAX_TOKENS", "16000")),
        history_days=int(os.getenv("NINEBOT_HISTORY_DAYS", "365")),
    )
