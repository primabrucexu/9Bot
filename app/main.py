from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db
from app.config import Settings, get_settings
from app.routers import api, pages


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db.init_db(resolved_settings.database_path)
        yield

    app = FastAPI(title="9Bot", lifespan=lifespan)
    app.state.settings = resolved_settings
    app.state.templates = Jinja2Templates(directory=str(resolved_settings.templates_dir))
    app.mount("/static", StaticFiles(directory=str(resolved_settings.static_dir)), name="static")

    app.include_router(pages.router)
    app.include_router(api.router)
    return app


app = create_app()
