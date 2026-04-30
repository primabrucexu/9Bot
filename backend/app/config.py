from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os

from dotenv import load_dotenv


_VALID_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


def _resolve_env_path(raw_path: str, project_root: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _resolve_optional_env_path(raw_path: str | None, project_root: Path) -> Path | None:
    if raw_path is None or not raw_path.strip():
        return None
    return _resolve_env_path(raw_path.strip(), project_root)


def _resolve_log_level(raw_value: str | None) -> str:
    log_level = (raw_value or "INFO").strip().upper()
    if log_level not in _VALID_LOG_LEVELS:
        raise ValueError("NINEBOT_LOG_LEVEL 必须是 CRITICAL、ERROR、WARNING、INFO 或 DEBUG。")
    return log_level


def _resolve_cors_allowed_origins(raw_value: str | None) -> tuple[str, ...]:
    if raw_value is None or not raw_value.strip():
        return ()

    origins = []
    for origin in raw_value.split(","):
        normalized = origin.strip().rstrip("/")
        if normalized:
            origins.append(normalized)
    return tuple(origins)


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
    log_level: str
    cors_allowed_origins: tuple[str, ...] = ()
    frontend_dist_dir: Path | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[1]
    repo_root = project_root.parent
    conf_env_path = repo_root / "conf" / ".env"
    legacy_env_path = project_root / ".env"

    if conf_env_path.exists():
        load_dotenv(conf_env_path)
    elif legacy_env_path.exists():
        load_dotenv(legacy_env_path)

    data_dir_raw = os.getenv("NINEBOT_DATA_DIR")
    database_path_raw = os.getenv("NINEBOT_DB_PATH")

    data_dir = _resolve_env_path(data_dir_raw or "data", repo_root)
    database_path = _resolve_env_path(database_path_raw, repo_root) if database_path_raw else data_dir / "9bot.db"

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
        log_level=_resolve_log_level(os.getenv("NINEBOT_LOG_LEVEL")),
        cors_allowed_origins=_resolve_cors_allowed_origins(os.getenv("NINEBOT_CORS_ORIGINS")),
        frontend_dist_dir=_resolve_optional_env_path(os.getenv("NINEBOT_FRONTEND_DIST"), project_root),
    )
