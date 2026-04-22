from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app import db
from app.services import indicators, market_data


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    settings = request.app.state.settings
    templates = request.app.state.templates

    rows = market_data.build_dashboard_rows(settings)
    latest_report = db.get_latest_report(settings.database_path)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "rows": rows,
            "latest_report": latest_report,
        },
    )


@router.get("/stocks/{symbol}", response_class=HTMLResponse)
def stock_detail(request: Request, symbol: str):
    settings = request.app.state.settings
    templates = request.app.state.templates

    stock = db.get_watchlist_item(settings.database_path, symbol)
    if stock is None:
        raise HTTPException(status_code=404, detail="未找到该自选股。")

    bars = db.get_daily_bars(settings.database_path, symbol, limit=240)
    summary = indicators.summarize_latest(bars) if not bars.empty else None

    return templates.TemplateResponse(
        request,
        "stock_detail.html",
        {
            "request": request,
            "stock": stock,
            "summary": summary,
        },
    )


@router.get("/reports/latest", response_class=HTMLResponse)
def latest_report(request: Request):
    settings = request.app.state.settings
    templates = request.app.state.templates

    report = db.get_latest_report(settings.database_path)
    return templates.TemplateResponse(
        request,
        "report_detail.html",
        {
            "request": request,
            "report": report,
        },
    )


@router.get("/reports/{report_date}", response_class=HTMLResponse, name="report_by_date")
def report_by_date(request: Request, report_date: str):
    settings = request.app.state.settings
    templates = request.app.state.templates

    report = db.get_report_by_date(settings.database_path, report_date)
    if report is None:
        raise HTTPException(status_code=404, detail="未找到该日报。")

    return templates.TemplateResponse(
        request,
        "report_detail.html",
        {
            "request": request,
            "report": report,
        },
    )
