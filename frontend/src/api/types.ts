export type BaseStockPoolRow = {
  symbol: string
  name: string
}

export type BaseStockPoolResponse = {
  rows: BaseStockPoolRow[]
  total: number
  offset: number
  limit: number
}

export type HotSector = {
  name: string
  count: number
  rank: number
}

export type LimitUpCopyRow = {
  symbol: string
  name: string
  sector: string
  score: number
  trade_date: string
  last_close: number
  last_limit_up_date: string
  limit_up_count_7d: number
  max_board_count: number
  daily_change_pct: number | null
  ma_status: string
  macd_bias: string
  rsi_state: string
  signals: string[]
}

export type LimitUpCopyResponse = {
  trade_date: string
  rows: LimitUpCopyRow[]
  total: number
  limit: number
  hot_sectors: HotSector[]
}

export type Stock = {
  symbol: string
  name: string
  market?: string | null
  board?: string | null
  is_st?: boolean | null
  is_active?: boolean | null
  note?: string | null
  sort_order?: number | null
  created_at?: string | null
}

export type StockSummary = {
  trade_date: string
  close: number
  daily_change_pct: number | null
  ma5: number | null
  ma10: number | null
  ma20: number | null
  ma60: number | null
  volume: number | null
  amount: number | null
  rsi14: number | null
  rsi_state: string
  macd_bias: string
  is_above_ma20: boolean
  signals: string[]
}

export type StockDetailResponse = {
  stock: Stock
  summary: StockSummary | null
  has_data: boolean
}

export type MarketOverviewIndex = {
  symbol: string
  name: string
  summary: StockSummary
}

export type MarketOverviewResponse = {
  indices: MarketOverviewIndex[]
}

export type ChartPayload = {
  dates: string[]
  candles: Array<Array<number | null>>
  volume: Array<number | null>
  ma5: Array<number | null>
  ma10: Array<number | null>
  ma20: Array<number | null>
  ma60: Array<number | null>
  macd: Array<number | null>
  macd_signal: Array<number | null>
  macd_hist: Array<number | null>
  rsi14: Array<number | null>
}

export type ReportResponse = {
  report_date: string
  report_markdown: string
  model_name: string
  created_at: string
}

export type MarketUniverseRefreshResponse = {
  ok: boolean
  scope: string
  count: number
}

export type MarketDataSyncRequest = {
  history_days?: number
  refresh_universe?: boolean
}

export type MarketDataSyncResponse = {
  ok: boolean
  scope: string
  history_days: number
  universe_count: number
  synced_count: number
  last_trade_date: string | null
}

export type ReportGenerationResponse = {
  ok: boolean
  report_date: string
}

export type JygsLoginFlow = {
  status: string
  message: string | null
  login_url: string | null
  updated_at: string | null
}

export type JygsDiagramEntry = {
  date: string
  status: string
  image_url: string
  source_image_url: string | null
  updated_at: string | null
}

export type JygsStatusResponse = {
  login_ready: boolean
  storage_state_path: string
  login_flow: JygsLoginFlow
  latest: JygsDiagramEntry | null
}

export type JygsLoginActionResponse = {
  ok: boolean
  status: JygsStatusResponse
}

export type JygsFetchResponse = {
  ok: boolean
  requested_dates: string[]
  skipped: string[]
  status: JygsStatusResponse
}
