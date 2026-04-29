from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import db
from app.services import indicators, jygs_diagram, market_data, report_generator, stock_screener


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


class AddWatchlistRequest(BaseModel):
    symbol: str


class WatchlistMutationResponse(BaseModel):
    ok: bool
    symbol: str | None = None
    name: str | None = None


class SyncWatchlistResponse(BaseModel):
    ok: bool
    count: int


class MarketUniverseRefreshResponse(BaseModel):
    ok: bool
    scope: str
    count: int


class MarketDataSyncRequest(BaseModel):
    history_days: int = 30
    refresh_universe: bool = False


class MarketDataSyncResponse(BaseModel):
    ok: bool
    scope: str
    history_days: int
    universe_count: int
    synced_count: int
    last_trade_date: str | None = None


class ReportGenerationResponse(BaseModel):
    ok: bool
    report_date: str


class WatchlistRowResponse(BaseModel):
    symbol: str
    name: str
    last_close: float | None
    daily_change_pct: float | None
    ma_status: str
    macd_bias: str
    rsi_state: str
    last_trade_date: str | None
    signals: list[str]
    has_data: bool


class WatchlistResponse(BaseModel):
    rows: list[WatchlistRowResponse]


class BaseStockPoolRowResponse(BaseModel):
    symbol: str
    name: str


class BaseStockPoolResponse(BaseModel):
    rows: list[BaseStockPoolRowResponse]
    total: int
    offset: int
    limit: int


class HotSectorResponse(BaseModel):
    name: str
    count: int
    rank: int


class LimitUpCopyRowResponse(BaseModel):
    symbol: str
    name: str
    sector: str
    score: int
    trade_date: str
    last_close: float
    last_limit_up_date: str
    limit_up_count_7d: int
    max_board_count: int
    daily_change_pct: float | None
    ma_status: str
    macd_bias: str
    rsi_state: str
    signals: list[str]


class LimitUpCopyResponse(BaseModel):
    trade_date: str
    rows: list[LimitUpCopyRowResponse]
    total: int
    limit: int
    hot_sectors: list[HotSectorResponse]


class StockResponse(BaseModel):
    symbol: str
    name: str
    market: str | None = None
    board: str | None = None
    is_st: bool | None = None
    is_active: bool | None = None
    note: str | None = None
    sort_order: int | None = None
    created_at: str | None = None


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


class MarketOverviewIndexResponse(BaseModel):
    symbol: str
    name: str
    summary: StockSummaryResponse


class MarketOverviewResponse(BaseModel):
    indices: list[MarketOverviewIndexResponse]


class JygsLoginFlowResponse(BaseModel):
    status: str
    message: str | None = None
    login_url: str | None = None
    updated_at: str | None = None


class JygsDiagramEntryResponse(BaseModel):
    date: str
    status: str
    image_url: str
    source_image_url: str | None = None
    updated_at: str | None = None


class JygsStatusResponse(BaseModel):
    login_ready: bool
    storage_state_path: str
    login_flow: JygsLoginFlowResponse
    latest: JygsDiagramEntryResponse | None = None


class JygsLoginActionResponse(BaseModel):
    ok: bool
    status: JygsStatusResponse


class JygsFetchResponse(BaseModel):
    ok: bool
    requested_dates: list[str]
    skipped: list[str]
    status: JygsStatusResponse


class ReportResponse(BaseModel):
    report_date: str
    report_markdown: str
    model_name: str
    created_at: str


@router.get("/watchlist", response_model=WatchlistResponse)
def get_watchlist(request: Request):
    settings = request.app.state.settings
    rows = market_data.build_watchlist_rows(settings)
    return WatchlistResponse(rows=[WatchlistRowResponse.model_validate(row) for row in rows])


@router.get("/stock-pool/base", response_model=BaseStockPoolResponse)
def get_base_stock_pool(
    q: str = "",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    try:
        payload = market_data.list_base_universe(query=q, limit=limit, offset=offset)
    except market_data.MarketDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BaseStockPoolResponse(
        rows=[BaseStockPoolRowResponse.model_validate(row) for row in payload["rows"]],
        total=payload["total"],
        offset=payload["offset"],
        limit=payload["limit"],
    )


@router.get("/stock-pool/limit-up-copy", response_model=LimitUpCopyResponse)
def get_limit_up_copy_candidates(
    request: Request,
    limit: int = Query(default=10, ge=1, le=50),
):
    settings = request.app.state.settings
    try:
        payload = stock_screener.screen_limit_up_copy(settings, limit=limit)
    except stock_screener.StockScreenerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return LimitUpCopyResponse(
        trade_date=payload["trade_date"],
        rows=[LimitUpCopyRowResponse.model_validate(row) for row in payload["rows"]],
        total=payload["total"],
        limit=payload["limit"],
        hot_sectors=[HotSectorResponse.model_validate(row) for row in payload["hot_sectors"]],
    )


@router.get("/market-overview", response_model=MarketOverviewResponse)
def get_market_overview(request: Request):
    settings = request.app.state.settings
    try:
        payload = market_data.build_market_overview(settings)
    except market_data.MarketDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MarketOverviewResponse(
        indices=[MarketOverviewIndexResponse.model_validate(row) for row in payload]
    )


@router.post("/market-data/universe/refresh", response_model=MarketUniverseRefreshResponse)
def refresh_market_universe(request: Request):
    settings = request.app.state.settings
    try:
        payload = market_data.refresh_stock_universe(settings)
    except market_data.MarketDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MarketUniverseRefreshResponse(ok=True, scope=payload["scope"], count=payload["count"])


@router.post("/market-data/sync", response_model=MarketDataSyncResponse)
def sync_market_data(request: Request, payload: MarketDataSyncRequest = MarketDataSyncRequest()):
    settings = request.app.state.settings
    logger.info(
        "Sync market data requested database_path=%s history_days=%s refresh_universe=%s",
        settings.database_path,
        payload.history_days,
        payload.refresh_universe,
    )
    try:
        result = market_data.sync_universe_daily_bars(
            settings,
            history_days=payload.history_days,
            refresh_universe=payload.refresh_universe,
        )
    except market_data.MarketDataError as exc:
        logger.warning(
            "Sync market data failed database_path=%s history_days=%s error=%s",
            settings.database_path,
            payload.history_days,
            exc,
            exc_info=exc.__cause__ is not None,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MarketDataSyncResponse(
        ok=True,
        scope=result["scope"],
        history_days=result["history_days"],
        universe_count=result["universe_count"],
        synced_count=result["synced_count"],
        last_trade_date=result.get("last_trade_date"),
    )


@router.get("/jygs/status", response_model=JygsStatusResponse)
def get_jygs_status(request: Request):
    settings = request.app.state.settings
    try:
        payload = jygs_diagram.get_status(settings)
    except jygs_diagram.JiuyangongsheDiagramError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _serialize_jygs_status(request, payload)


@router.post("/jygs/login/start", response_model=JygsLoginActionResponse)
def start_jygs_login(request: Request):
    settings = request.app.state.settings
    try:
        payload = jygs_diagram.start_login(settings)
    except jygs_diagram.JiuyangongsheDiagramError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return JygsLoginActionResponse(ok=True, status=_serialize_jygs_status(request, payload))


@router.post("/jygs/login/complete", response_model=JygsLoginActionResponse)
def complete_jygs_login(request: Request):
    settings = request.app.state.settings
    try:
        payload = jygs_diagram.complete_login(settings)
    except jygs_diagram.JiuyangongsheDiagramError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return JygsLoginActionResponse(ok=True, status=_serialize_jygs_status(request, payload))


@router.post("/jygs/diagram/fetch", response_model=JygsFetchResponse)
def fetch_latest_jygs_diagram(request: Request):
    settings = request.app.state.settings
    try:
        summary = jygs_diagram.fetch_diagrams(settings, latest=True, force=False)
        status_payload = jygs_diagram.get_status(settings)
    except jygs_diagram.JiuyangongsheDiagramError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return JygsFetchResponse(
        ok=True,
        requested_dates=list(summary["requested_dates"]),
        skipped=list(summary["skipped"]),
        status=_serialize_jygs_status(request, status_payload),
    )


@router.get("/jygs/diagram/image/{trade_date}", name="get_jygs_diagram_image")
def get_jygs_diagram_image(request: Request, trade_date: str):
    settings = request.app.state.settings
    try:
        image_path = jygs_diagram.resolve_diagram_file(settings, trade_date)
    except jygs_diagram.JiuyangongsheDiagramError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FileResponse(image_path)


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


@router.post("/watchlist/sync", response_model=SyncWatchlistResponse)
def sync_watchlist(request: Request):
    settings = request.app.state.settings
    logger.info("Sync watchlist requested database_path=%s", settings.database_path)
    try:
        synced = market_data.sync_watchlist_daily_bars(settings)
    except market_data.MarketDataError as exc:
        logger.warning(
            "Sync watchlist failed database_path=%s error=%s",
            settings.database_path,
            exc,
            exc_info=exc.__cause__ is not None,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("Sync watchlist succeeded database_path=%s count=%s", settings.database_path, len(synced))
    return SyncWatchlistResponse(ok=True, count=len(synced))


@router.get("/stocks/{symbol}", response_model=StockDetailResponse)
def get_stock_detail(request: Request, symbol: str):
    settings = request.app.state.settings
    bars = db.get_daily_bars(settings.database_path, symbol, limit=240)
    stock = db.get_stock_universe_item(settings.database_path, symbol)
    legacy_stock = db.get_watchlist_item(settings.database_path, symbol)
    resolved_name: str | None = None

    if stock is None and legacy_stock is None:
        try:
            resolved_name = market_data.resolve_symbol_name(symbol)
        except market_data.MarketDataError:
            resolved_name = None

    if stock is None and legacy_stock is None and bars.empty and resolved_name is None:
        raise HTTPException(status_code=404, detail="未找到该股票。")

    if stock is None:
        stock_payload = {
            "symbol": symbol,
            "name": legacy_stock["name"] if legacy_stock else resolved_name or symbol,
        }
    else:
        stock_payload = dict(stock)

    if legacy_stock:
        stock_payload.update(
            note=legacy_stock.get("note"),
            sort_order=legacy_stock.get("sort_order"),
            created_at=legacy_stock.get("created_at"),
        )

    summary = indicators.summarize_latest(bars) if not bars.empty else None
    return StockDetailResponse(
        stock=StockResponse.model_validate(stock_payload),
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
        raise HTTPException(status_code=404, detail="该股票还没有可用历史数据，请先同步日线数据。")
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


def _serialize_jygs_status(request: Request, payload: dict) -> JygsStatusResponse:
    latest = payload.get("latest")
    return JygsStatusResponse(
        login_ready=bool(payload["login_ready"]),
        storage_state_path=str(payload["storage_state_path"]),
        login_flow=JygsLoginFlowResponse.model_validate(payload["login_flow"]),
        latest=_serialize_jygs_entry(request, latest) if latest else None,
    )


def _serialize_jygs_entry(request: Request, entry: dict) -> JygsDiagramEntryResponse:
    image_url = str(request.url_for("get_jygs_diagram_image", trade_date=entry["date"]))
    return JygsDiagramEntryResponse(
        date=entry["date"],
        status=entry["status"],
        image_url=image_url,
        source_image_url=entry.get("source_image_url"),
        updated_at=entry.get("updated_at"),
    )


def _serialize_report(report: dict) -> ReportResponse:
    return ReportResponse(
        report_date=report["report_date"],
        report_markdown=report["report_markdown"],
        model_name=report["model_name"],
        created_at=report["created_at"],
    )
