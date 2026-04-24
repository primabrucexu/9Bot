export type DashboardRow = {
  symbol: string
  name: string
  latest_close: number | null
  daily_change_pct: number | null
  ma_status: string
  macd_bias: string
  rsi_state: string
  last_trade_date: string | null
  signals: string[]
  has_data: boolean
}

export type ReportPreview = {
  report_date: string
  preview_markdown: string
  model_name: string
  created_at: string
}

export type DashboardResponse = {
  rows: DashboardRow[]
  latest_report: ReportPreview | null
}

export type Stock = {
  symbol: string
  name: string
  note: string | null
  sort_order: number
  created_at: string
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

export type WatchlistMutationResponse = {
  ok: boolean
  symbol?: string
  name?: string
}

export type RefreshWatchlistResponse = {
  ok: boolean
  count: number
}

export type ReportGenerationResponse = {
  ok: boolean
  report_date: string
}
