from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app import db
from app.services import indicators, market_data, report_generator


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


class AddWatchlistRequest(BaseModel):
    symbol: str


class WatchlistMutationResponse(BaseModel):
    ok: bool
    symbol: str | None = None
    name: str | None = None


class RefreshWatchlistResponse(BaseModel):
    ok: bool
    count: int


class ReportGenerationResponse(BaseModel):
    ok: bool
    report_date: str


class DashboardRowResponse(BaseModel):
    symbol: str
    name: str
    latest_close: float | None
    daily_change_pct: float | None
    ma_status: str
    macd_bias: str
    rsi_state: str
    last_trade_date: str | None
    signals: list[str]
    has_data: bool


class ReportPreviewResponse(BaseModel):
    report_date: str
    preview_markdown: str
    model_name: str
    created_at: str


class DashboardResponse(BaseModel):
    rows: list[DashboardRowResponse]
    latest_report: ReportPreviewResponse | None


class StockResponse(BaseModel):
    symbol: str
    name: str
    note: str | None = None
    sort_order: int
    created_at: str


class StockSummaryResponse(BaseModel):
    trade_date: str
    close: float
    daily_change_pct: float | None
    ma5: float | None
    ma10: float | None
    ma20: float | None
    ma60: float | None
    volume: float | None
    amount: float | None
    rsi14: float | None
    rsi_state: str
    macd_bias: str
    is_above_ma20: bool
    signals: list[str]


class StockDetailResponse(BaseModel):
    stock: StockResponse
    summary: StockSummaryResponse | None
    has_data: bool


class ReportResponse(BaseModel):
    report_date: str
    report_markdown: str
    model_name: str
    created_at: str


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(request: Request):
    settings = request.app.state.settings
    rows = market_data.build_dashboard_rows(settings)
    latest_report = db.get_latest_report(settings.database_path)
    return DashboardResponse(
        rows=[DashboardRowResponse.model_validate(row) for row in rows],
        latest_report=_serialize_report_preview(latest_report),
    )


@router.post("/watchlist", response_model=WatchlistMutationResponse)
def add_watchlist(request: Request, payload: AddWatchlistRequest):
    settings = request.app.state.settings
    logger.info("Add watchlist requested symbol=%s database_path=%s", payload.symbol, settings.database_path)
    try:
        stock = market_data.add_watchlist_symbol(settings, payload.symbol)
    except market_data.MarketDataError as exc:
        logger.warning(
            "Add watchlist failed symbol=%s database_path=%s error=%s",
            payload.symbol,
            settings.database_path,
            exc,
            exc_info=exc.__cause__ is not None,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.info(
        "Add watchlist succeeded symbol=%s name=%s database_path=%s",
        stock["symbol"],
        stock["name"],
        settings.database_path,
    )
    return WatchlistMutationResponse(ok=True, symbol=stock["symbol"], name=stock["name"])


@router.delete("/watchlist/{symbol}", response_model=WatchlistMutationResponse)
def remove_watchlist(request: Request, symbol: str):
    settings = request.app.state.settings
    try:
        market_data.remove_watchlist_symbol(settings, symbol)
    except market_data.MarketDataError as exc:
        logger.warning(
            "Remove watchlist failed symbol=%s database_path=%s error=%s",
            symbol,
            settings.database_path,
            exc,
            exc_info=exc.__cause__ is not None,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WatchlistMutationResponse(ok=True, symbol=symbol)


@router.post("/watchlist/refresh", response_model=RefreshWatchlistResponse)
def refresh_watchlist(request: Request):
    settings = request.app.state.settings
    logger.info("Refresh watchlist requested database_path=%s", settings.database_path)
    try:
        refreshed = market_data.refresh_watchlist(settings)
    except market_data.MarketDataError as exc:
        logger.warning(
            "Refresh watchlist failed database_path=%s error=%s",
            settings.database_path,
            exc,
            exc_info=exc.__cause__ is not None,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("Refresh watchlist succeeded database_path=%s count=%s", settings.database_path, len(refreshed))
    return RefreshWatchlistResponse(ok=True, count=len(refreshed))


@router.get("/stocks/{symbol}", response_model=StockDetailResponse)
def get_stock_detail(request: Request, symbol: str):
    settings = request.app.state.settings
    stock = db.get_watchlist_item(settings.database_path, symbol)
    if stock is None:
        raise HTTPException(status_code=404, detail="未找到该自选股。")

    bars = db.get_daily_bars(settings.database_path, symbol, limit=240)
    summary = indicators.summarize_latest(bars) if not bars.empty else None
    return StockDetailResponse(
        stock=StockResponse.model_validate(stock),
        summary=StockSummaryResponse.model_validate(summary) if summary else None,
        has_data=not bars.empty,
    )


@router.get("/stocks/{symbol}/chart", name="get_stock_chart")
def get_stock_chart(request: Request, symbol: str):
    settings = request.app.state.settings
    logger.info("Stock chart requested symbol=%s database_path=%s", symbol, settings.database_path)
    bars = db.get_daily_bars(settings.database_path, symbol, limit=240)
    if bars.empty:
        logger.warning(
            "Chart data missing symbol=%s database_path=%s",
            symbol,
            settings.database_path,
        )
        raise HTTPException(status_code=404, detail="该股票还没有可用历史数据，请先刷新行情。")
    logger.info("Stock chart loaded symbol=%s database_path=%s bars=%s", symbol, settings.database_path, len(bars))
    return indicators.to_chart_payload(bars)


@router.get("/reports/latest", response_model=ReportResponse)
def get_latest_report(request: Request):
    settings = request.app.state.settings
    report = db.get_latest_report(settings.database_path)
    if report is None:
        raise HTTPException(status_code=404, detail="还没有可用日报。")
    return _serialize_report(report)


@router.get("/reports/{report_date}", response_model=ReportResponse)
def get_report_by_date(request: Request, report_date: str):
    settings = request.app.state.settings
    report = db.get_report_by_date(settings.database_path, report_date)
    if report is None:
        raise HTTPException(status_code=404, detail="未找到该日报。")
    return _serialize_report(report)


@router.post("/reports", response_model=ReportGenerationResponse)
def generate_report(request: Request):
    settings = request.app.state.settings
    try:
        report = report_generator.generate_daily_report(settings)
    except report_generator.ReportGenerationError as exc:
        logger.warning(
            "Generate report failed database_path=%s error=%s",
            settings.database_path,
            exc,
            exc_info=exc.__cause__ is not None,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ReportGenerationResponse(ok=True, report_date=report["report_date"])


def _serialize_report_preview(report: dict | None) -> ReportPreviewResponse | None:
    if report is None:
        return None

    markdown = report["report_markdown"]
    preview = markdown[:420]
    if len(markdown) > 420:
        preview = f"{preview}..."

    return ReportPreviewResponse(
        report_date=report["report_date"],
        preview_markdown=preview,
        model_name=report["model_name"],
        created_at=report["created_at"],
    )


def _serialize_report(report: dict) -> ReportResponse:
    return ReportResponse(
        report_date=report["report_date"],
        report_markdown=report["report_markdown"],
        model_name=report["model_name"],
        created_at=report["created_at"],
    )
