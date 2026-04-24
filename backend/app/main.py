from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app import db
from app.config import Settings, get_settings
from app.routers import api


logger = logging.getLogger(__name__)


def configure_logging(log_level: str) -> None:
    level = getattr(logging, log_level, logging.INFO)
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )
    root_logger.setLevel(level)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database_exists = resolved_settings.database_path.exists()
        logger.info(
            "9Bot startup cwd=%s project_root=%s data_dir=%s database_path=%s database_exists=%s",
            Path.cwd(),
            resolved_settings.project_root,
            resolved_settings.data_dir,
            resolved_settings.database_path,
            database_exists,
        )
        db.init_db(resolved_settings.database_path)
        yield

    app = FastAPI(title="9Bot API", lifespan=lifespan)
    app.state.settings = resolved_settings

    if resolved_settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved_settings.cors_allowed_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(api.router)
    return app


def _get_reload_setting() -> bool:
    return os.getenv("NINEBOT_RELOAD", "true").lower() in {"1", "true", "yes", "on"}


def main() -> None:
    host = os.getenv("NINEBOT_HOST", "127.0.0.1")
    port = int(os.getenv("NINEBOT_PORT", "8000"))
    reload = _get_reload_setting()
    settings = app.state.settings
    target = "app.main:app" if reload else app
    uvicorn.run(target, host=host, port=port, reload=reload, log_level=settings.log_level.lower())


app = create_app()


if __name__ == "__main__":
    main()
