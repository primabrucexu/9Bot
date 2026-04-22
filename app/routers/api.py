from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app import db
from app.services import indicators, market_data, report_generator


router = APIRouter(prefix="/api")


class AddWatchlistRequest(BaseModel):
    symbol: str


@router.post("/watchlist")
def add_watchlist(request: Request, payload: AddWatchlistRequest):
    settings = request.app.state.settings
    try:
        stock = market_data.add_watchlist_symbol(settings, payload.symbol)
    except market_data.MarketDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "ok": True,
        "symbol": stock["symbol"],
        "name": stock["name"],
    }


@router.delete("/watchlist/{symbol}")
def remove_watchlist(request: Request, symbol: str):
    settings = request.app.state.settings
    try:
        market_data.remove_watchlist_symbol(settings, symbol)
    except market_data.MarketDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/refresh")
def refresh_watchlist(request: Request):
    settings = request.app.state.settings
    try:
        refreshed = market_data.refresh_watchlist(settings)
    except market_data.MarketDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "count": len(refreshed)}


@router.get("/stocks/{symbol}/chart", name="get_stock_chart")
def get_stock_chart(request: Request, symbol: str):
    settings = request.app.state.settings
    bars = db.get_daily_bars(settings.database_path, symbol, limit=240)
    if bars.empty:
        raise HTTPException(status_code=404, detail="该股票还没有可用历史数据，请先刷新行情。")
    return indicators.to_chart_payload(bars)


@router.post("/reports/generate")
def generate_report(request: Request):
    settings = request.app.state.settings
    try:
        report = report_generator.generate_daily_report(settings)
    except report_generator.ReportGenerationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "ok": True,
        "report_date": report["report_date"],
        "redirect_url": str(request.url_for("report_by_date", report_date=report["report_date"])),
    }
