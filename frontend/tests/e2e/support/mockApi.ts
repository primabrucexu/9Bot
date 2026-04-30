import type { Page, Route } from '@playwright/test'

type BaseStockPoolRow = {
  symbol: string
  name: string
}

type LimitUpCopyRow = {
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

type WatchlistRow = {
  symbol: string
  name: string
  last_close: number | null
  daily_change_pct: number | null
  ma_status: string
  macd_bias: string
  rsi_state: string
  last_trade_date: string | null
  signals: string[]
  has_data: boolean
}

type StockSummary = {
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

type StockDetailResponse = {
  stock: {
    symbol: string
    name: string
    market?: string | null
    board?: string | null
    is_st?: boolean | null
    is_active?: boolean | null
    note: string | null
    sort_order: number
    created_at: string
  }
  summary: StockSummary | null
  has_data: boolean
}

type MarketOverviewResponse = {
  indices: Array<{
    symbol: string
    name: string
    summary: StockSummary
  }>
}

type LimitUpCopyResponse = {
  trade_date: string
  rows: LimitUpCopyRow[]
  total: number
  limit: number
  hot_sectors: Array<{
    name: string
    count: number
    rank: number
  }>
}

type ChartPayload = {
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

type ReportResponse = {
  report_date: string
  report_markdown: string
  model_name: string
  created_at: string
}

type JygsLoginFlow = {
  status: string
  message: string | null
  login_url: string | null
  updated_at: string | null
}

type JygsDiagramEntry = {
  date: string
  status: string
  image_url: string
  source_image_url: string | null
  updated_at: string | null
}

type JygsStatusResponse = {
  login_ready: boolean
  storage_state_path: string
  login_flow: JygsLoginFlow
  latest: JygsDiagramEntry | null
}

type MockApiState = {
  stockPoolRows: BaseStockPoolRow[]
  limitUpCopy: LimitUpCopyResponse
  limitUpCopyStatus: number
  limitUpCopyErrorDetail: string
  watchlistRows: WatchlistRow[]
  stockDetails: Record<string, StockDetailResponse>
  marketUniverseCount: number
  marketDataLastTradeDate: string | null
  marketDataSyncStatus: number
  marketDataSyncErrorDetail: string
  marketOverview: MarketOverviewResponse
  marketOverviewStatus: number
  marketOverviewErrorDetail: string
  charts: Record<string, ChartPayload>
  reportsByDate: Record<string, ReportResponse>
  latestReportDate: string | null
  generatedReportDate: string
  jygsStatus: JygsStatusResponse
  jygsStatusCode: number
  jygsStatusErrorDetail: string
  jygsLoginStartCode: number
  jygsLoginStartErrorDetail: string
  jygsLoginCompleteCode: number
  jygsLoginCompleteErrorDetail: string
  jygsFetchCode: number
  jygsFetchErrorDetail: string
}

type MockApiOverrides = Partial<MockApiState>

function buildChartPayload(startClose: number): ChartPayload {
  return {
    dates: ['2026-04-22', '2026-04-23', '2026-04-24', '2026-04-25'],
    candles: [
      [startClose - 8, startClose - 3, startClose - 10, startClose + 6],
      [startClose - 4, startClose + 12, startClose - 7, startClose + 18],
      [startClose + 11, startClose + 9, startClose + 3, startClose + 15],
      [startClose + 10, startClose + 16, startClose + 8, startClose + 20],
    ],
    volume: [1800000, 2200000, 1950000, 2400000],
    ma5: [null, null, null, startClose + 8],
    ma10: [null, null, null, startClose + 4],
    ma20: [null, null, null, startClose],
    ma60: [null, null, null, startClose - 10],
    macd: [0.12, 0.2, 0.18, 0.26],
    macd_signal: [0.08, 0.12, 0.15, 0.19],
    macd_hist: [0.04, 0.08, 0.03, 0.07],
    rsi14: [48, 57, 54, 61],
  }
}

function createDefaultState(): MockApiState {
  const stockPoolRows: BaseStockPoolRow[] = [
    {
      symbol: '600519',
      name: '贵州茅台',
    },
    {
      symbol: '000001',
      name: '平安银行',
    },
    {
      symbol: '002594',
      name: '比亚迪',
    },
  ]

  const limitUpCopy: LimitUpCopyResponse = {
    trade_date: '2026-04-27',
    rows: [
      {
        symbol: '600519',
        name: '贵州茅台',
        sector: '白酒',
        score: 86,
        trade_date: '2026-04-27',
        last_close: 1688.88,
        last_limit_up_date: '2026-04-24',
        limit_up_count_7d: 2,
        max_board_count: 2,
        daily_change_pct: 1.26,
        ma_status: 'MA20 上方',
        macd_bias: '多头',
        rsi_state: '中性',
        signals: ['热点板块第 1 名：白酒', '近 7 个交易日涨停 2 次', '均线与 MACD 维持强势'],
      },
      {
        symbol: '002594',
        name: '比亚迪',
        sector: '汽车整车',
        score: 79,
        trade_date: '2026-04-27',
        last_close: 268.4,
        last_limit_up_date: '2026-04-23',
        limit_up_count_7d: 1,
        max_board_count: 1,
        daily_change_pct: 2.35,
        ma_status: 'MA20 上方',
        macd_bias: '多头',
        rsi_state: '中性',
        signals: ['热点板块第 2 名：汽车整车', '近 7 个交易日涨停 1 次'],
      },
    ],
    total: 2,
    limit: 10,
    hot_sectors: [
      { name: '白酒', count: 8, rank: 1 },
      { name: '汽车整车', count: 6, rank: 2 },
    ],
  }

  const watchlistRows: WatchlistRow[] = [
    {
      symbol: '600519',
      name: '贵州茅台',
      last_close: 1688.88,
      daily_change_pct: 1.26,
      ma_status: 'MA20 上方',
      macd_bias: '多头',
      rsi_state: '中性',
      last_trade_date: '2026-04-25',
      signals: ['收盘价位于 MA20 上方', 'MACD 保持多头结构'],
      has_data: true,
    },
    {
      symbol: '000001',
      name: '平安银行',
      last_close: 12.36,
      daily_change_pct: -0.48,
      ma_status: 'MA20 下方',
      macd_bias: '空头',
      rsi_state: '中性',
      last_trade_date: '2026-04-25',
      signals: ['收盘价位于 MA20 下方', 'MACD 保持空头结构'],
      has_data: true,
    },
  ]

  const stockDetails: Record<string, StockDetailResponse> = {
    '600519': {
      stock: {
        symbol: '600519',
        name: '贵州茅台',
        market: 'SSE',
        board: 'main',
        is_st: false,
        is_active: true,
        note: null,
        sort_order: 1,
        created_at: '2026-04-25T09:00:00+08:00',
      },
      summary: {
        trade_date: '2026-04-25',
        close: 1688.88,
        daily_change_pct: 1.26,
        ma5: 1679.21,
        ma10: 1652.37,
        ma20: 1608.56,
        ma60: 1542.18,
        volume: 2400000,
        amount: 4050000000,
        rsi14: 61.2,
        rsi_state: '中性',
        macd_bias: '多头',
        is_above_ma20: true,
        signals: ['收盘价位于 MA20 上方', 'MACD 保持多头结构', 'RSI 处于中性区间'],
      },
      has_data: true,
    },
    '000001': {
      stock: {
        symbol: '000001',
        name: '平安银行',
        market: 'SZSE',
        board: 'main',
        is_st: false,
        is_active: true,
        note: null,
        sort_order: 2,
        created_at: '2026-04-25T09:01:00+08:00',
      },
      summary: {
        trade_date: '2026-04-25',
        close: 12.36,
        daily_change_pct: -0.48,
        ma5: 12.5,
        ma10: 12.63,
        ma20: 12.79,
        ma60: 13.12,
        volume: 33500000,
        amount: 420000000,
        rsi14: 43.1,
        rsi_state: '中性',
        macd_bias: '空头',
        is_above_ma20: false,
        signals: ['收盘价位于 MA20 下方', 'MACD 保持空头结构', 'RSI 处于中性区间'],
      },
      has_data: true,
    },
    '002594': {
      stock: {
        symbol: '002594',
        name: '比亚迪',
        market: 'SZSE',
        board: 'main',
        is_st: false,
        is_active: true,
        note: null,
        sort_order: 3,
        created_at: '2026-04-25T09:02:00+08:00',
      },
      summary: null,
      has_data: false,
    },
  }

  const marketOverview: MarketOverviewResponse = {
    indices: [
      {
        symbol: 'sh000001',
        name: '上证指数',
        summary: {
          trade_date: '2026-04-25',
          close: 3288.41,
          daily_change_pct: 0.82,
          ma5: 3268.11,
          ma10: 3244.56,
          ma20: 3208.34,
          ma60: 3138.92,
          volume: 60503179800,
          amount: null,
          rsi14: 58.2,
          rsi_state: '中性',
          macd_bias: '多头',
          is_above_ma20: true,
          signals: ['收盘价位于 MA20 上方', 'MACD 保持多头结构'],
        },
      },
      {
        symbol: 'sz399001',
        name: '深证成指',
        summary: {
          trade_date: '2026-04-25',
          close: 10456.32,
          daily_change_pct: -0.36,
          ma5: 10502.18,
          ma10: 10524.41,
          ma20: 10488.66,
          ma60: 10196.75,
          volume: 70972943878,
          amount: null,
          rsi14: 47.5,
          rsi_state: '中性',
          macd_bias: '空头',
          is_above_ma20: false,
          signals: ['收盘价位于 MA20 下方', 'MACD 保持空头结构'],
        },
      },
      {
        symbol: 'sz399006',
        name: '创业板指',
        summary: {
          trade_date: '2026-04-25',
          close: 2104.78,
          daily_change_pct: 1.14,
          ma5: 2081.55,
          ma10: 2068.72,
          ma20: 2044.9,
          ma60: 1988.43,
          volume: 22796018188,
          amount: null,
          rsi14: 60.1,
          rsi_state: '中性',
          macd_bias: '多头',
          is_above_ma20: true,
          signals: ['收盘价位于 MA20 上方', 'MACD 保持多头结构'],
        },
      },
    ],
  }

  const jygsStatus: JygsStatusResponse = {
    login_ready: false,
    storage_state_path: 'D:/dev/9Bot/data/jygs/auth/storage-state.json',
    login_flow: {
      status: 'idle',
      message: null,
      login_url: null,
      updated_at: '2026-04-29T09:00:00+08:00',
    },
    latest: null,
  }

  return {
    stockPoolRows,
    limitUpCopy,
    limitUpCopyStatus: 200,
    limitUpCopyErrorDetail: '获取选股结果失败',
    watchlistRows,
    stockDetails,
    marketUniverseCount: 5321,
    marketDataLastTradeDate: '2026-04-25',
    marketDataSyncStatus: 200,
    marketDataSyncErrorDetail: '同步市场数据失败',
    marketOverview,
    marketOverviewStatus: 200,
    marketOverviewErrorDetail: '获取大盘数据失败',
    charts: {
      '600519': buildChartPayload(1672),
      '000001': buildChartPayload(12.1),
    },
    reportsByDate: {
      '2026-04-25': {
        report_date: '2026-04-25',
        report_markdown: '# 2026-04-25 市场观察日报\n\n- 贵州茅台维持多头结构\n- 平安银行仍偏弱。',
        model_name: 'claude-opus-4-6',
        created_at: '2026-04-25T18:00:00+08:00',
      },
    },
    latestReportDate: '2026-04-25',
    generatedReportDate: '2026-04-25',
    jygsStatus,
    jygsStatusCode: 200,
    jygsStatusErrorDetail: '获取韭研公社状态失败',
    jygsLoginStartCode: 200,
    jygsLoginStartErrorDetail: '启动网页登录失败',
    jygsLoginCompleteCode: 200,
    jygsLoginCompleteErrorDetail: '保存登录态失败',
    jygsFetchCode: 200,
    jygsFetchErrorDetail: '抓取最新简图失败',
  }
}

export async function registerMockApi(page: Page, overrides: MockApiOverrides = {}) {
  const defaultState = createDefaultState()
  const state: MockApiState = {
    stockPoolRows: overrides.stockPoolRows ?? defaultState.stockPoolRows,
    limitUpCopy: overrides.limitUpCopy ?? defaultState.limitUpCopy,
    limitUpCopyStatus: overrides.limitUpCopyStatus ?? defaultState.limitUpCopyStatus,
    limitUpCopyErrorDetail: overrides.limitUpCopyErrorDetail ?? defaultState.limitUpCopyErrorDetail,
    watchlistRows: overrides.watchlistRows ?? defaultState.watchlistRows,
    stockDetails: { ...defaultState.stockDetails, ...overrides.stockDetails },
    marketUniverseCount: overrides.marketUniverseCount ?? defaultState.marketUniverseCount,
    marketDataLastTradeDate: overrides.marketDataLastTradeDate ?? defaultState.marketDataLastTradeDate,
    marketDataSyncStatus: overrides.marketDataSyncStatus ?? defaultState.marketDataSyncStatus,
    marketDataSyncErrorDetail:
      overrides.marketDataSyncErrorDetail ?? defaultState.marketDataSyncErrorDetail,
    marketOverview: overrides.marketOverview ?? defaultState.marketOverview,
    marketOverviewStatus: overrides.marketOverviewStatus ?? defaultState.marketOverviewStatus,
    marketOverviewErrorDetail:
      overrides.marketOverviewErrorDetail ?? defaultState.marketOverviewErrorDetail,
    charts: { ...defaultState.charts, ...overrides.charts },
    reportsByDate: { ...defaultState.reportsByDate, ...overrides.reportsByDate },
    latestReportDate: overrides.latestReportDate ?? defaultState.latestReportDate,
    generatedReportDate: overrides.generatedReportDate ?? defaultState.generatedReportDate,
    jygsStatus: overrides.jygsStatus ?? defaultState.jygsStatus,
    jygsStatusCode: overrides.jygsStatusCode ?? defaultState.jygsStatusCode,
    jygsStatusErrorDetail: overrides.jygsStatusErrorDetail ?? defaultState.jygsStatusErrorDetail,
    jygsLoginStartCode: overrides.jygsLoginStartCode ?? defaultState.jygsLoginStartCode,
    jygsLoginStartErrorDetail:
      overrides.jygsLoginStartErrorDetail ?? defaultState.jygsLoginStartErrorDetail,
    jygsLoginCompleteCode: overrides.jygsLoginCompleteCode ?? defaultState.jygsLoginCompleteCode,
    jygsLoginCompleteErrorDetail:
      overrides.jygsLoginCompleteErrorDetail ?? defaultState.jygsLoginCompleteErrorDetail,
    jygsFetchCode: overrides.jygsFetchCode ?? defaultState.jygsFetchCode,
    jygsFetchErrorDetail: overrides.jygsFetchErrorDetail ?? defaultState.jygsFetchErrorDetail,
  }

  await page.route('http://127.0.0.1:8000/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname

    if (request.method() === 'GET' && path === '/api/jygs/status') {
      if (state.jygsStatusCode !== 200) {
        return json(route, { detail: state.jygsStatusErrorDetail }, state.jygsStatusCode)
      }
      return json(route, state.jygsStatus)
    }

    if (request.method() === 'POST' && path === '/api/jygs/login/start') {
      if (state.jygsLoginStartCode !== 200) {
        return json(route, { detail: state.jygsLoginStartErrorDetail }, state.jygsLoginStartCode)
      }
      state.jygsStatus = {
        ...state.jygsStatus,
        login_ready: false,
        login_flow: {
          status: 'waiting',
          message: '请在打开的 Edge 窗口中完成登录，然后回到 9Bot 页面点击“我已登录，保存登录态”。',
          login_url: 'https://www.jiuyangongshe.com/action/2026-04-29',
          updated_at: '2026-04-29T09:10:00+08:00',
        },
      }
      return json(route, { ok: true, status: state.jygsStatus })
    }

    if (request.method() === 'POST' && path === '/api/jygs/login/complete') {
      if (state.jygsLoginCompleteCode !== 200) {
        return json(route, { detail: state.jygsLoginCompleteErrorDetail }, state.jygsLoginCompleteCode)
      }
      state.jygsStatus = {
        ...state.jygsStatus,
        login_ready: true,
        login_flow: {
          status: 'saved',
          message: '登录态已保存。',
          login_url: 'https://www.jiuyangongshe.com/action/2026-04-29',
          updated_at: '2026-04-29T09:12:00+08:00',
        },
      }
      return json(route, { ok: true, status: state.jygsStatus })
    }

    if (request.method() === 'POST' && path === '/api/jygs/diagram/fetch') {
      if (state.jygsFetchCode !== 200) {
        return json(route, { detail: state.jygsFetchErrorDetail }, state.jygsFetchCode)
      }
      state.jygsStatus = {
        ...state.jygsStatus,
        login_ready: true,
        latest: {
          date: '2026-04-29',
          status: 'downloaded',
          image_url: 'http://127.0.0.1:8000/api/jygs/diagram/image/2026-04-29',
          source_image_url: 'https://cdn.example.com/jygs/2026-04-29.png',
          updated_at: '2026-04-29T09:20:00+08:00',
        },
      }
      return json(route, {
        ok: true,
        requested_dates: ['2026-04-29'],
        skipped: [],
        status: state.jygsStatus,
      })
    }

    if (request.method() === 'GET' && path.startsWith('/api/jygs/diagram/image/')) {
      const tradeDate = path.split('/').pop() ?? 'unknown'
      return svg(route, `韭研公社 ${tradeDate}`)
    }

    if (request.method() === 'POST' && path === '/api/market-data/universe/refresh') {
      return json(route, { ok: true, scope: 'full-a-share', count: state.marketUniverseCount })
    }

    if (request.method() === 'POST' && path === '/api/market-data/sync') {
      if (state.marketDataSyncStatus !== 200) {
        return json(route, { detail: state.marketDataSyncErrorDetail }, state.marketDataSyncStatus)
      }
      const payload = parseRequestBody(request.postData())
      const historyDays = typeof payload.history_days === 'number' ? payload.history_days : 30
      return json(route, {
        ok: true,
        scope: 'full-a-share',
        history_days: historyDays,
        universe_count: state.marketUniverseCount,
        synced_count: state.marketUniverseCount,
        last_trade_date: state.marketDataLastTradeDate,
      })
    }

    if (request.method() === 'GET' && path === '/api/market-overview') {
      if (state.marketOverviewStatus !== 200) {
        return json(route, { detail: state.marketOverviewErrorDetail }, state.marketOverviewStatus)
      }
      return json(route, state.marketOverview)
    }

    if (request.method() === 'GET' && path === '/api/stock-pool/limit-up-copy') {
      if (state.limitUpCopyStatus !== 200) {
        return json(route, { detail: state.limitUpCopyErrorDetail }, state.limitUpCopyStatus)
      }
      return json(route, state.limitUpCopy)
    }

    if (request.method() === 'GET' && path === '/api/stock-pool/base') {
      const query = (url.searchParams.get('q') ?? '').trim().toLowerCase()
      const limit = Number(url.searchParams.get('limit') ?? '50')
      const offset = Number(url.searchParams.get('offset') ?? '0')
      const matchedRows = state.stockPoolRows.filter(
        (row) => !query || row.symbol.includes(query) || row.name.toLowerCase().includes(query),
      )
      return json(route, {
        rows: matchedRows.slice(offset, offset + limit),
        total: matchedRows.length,
        offset,
        limit,
      })
    }

    if (request.method() === 'GET' && path === '/api/watchlist') {
      return json(route, { rows: state.watchlistRows })
    }

    if (request.method() === 'POST' && path === '/api/watchlist') {
      const payload = parseRequestBody(request.postData())
      const symbol = typeof payload.symbol === 'string' ? payload.symbol : ''
      const stock = state.stockPoolRows.find((row) => row.symbol === symbol)
      if (!stock) {
        return json(route, { detail: '仅支持上证、深证范围内且名称不含 ST 的股票。' }, 400)
      }

      if (!state.watchlistRows.some((row) => row.symbol === symbol)) {
        state.watchlistRows.push({
          symbol,
          name: stock.name,
          last_close: null,
          daily_change_pct: null,
          ma_status: '未同步',
          macd_bias: '未同步',
          rsi_state: '未同步',
          last_trade_date: null,
          signals: [],
          has_data: false,
        })
      }

      state.stockDetails[symbol] ??= {
        stock: {
          symbol,
          name: stock.name,
          note: null,
          sort_order: state.watchlistRows.length,
          created_at: '2026-04-25T09:03:00+08:00',
        },
        summary: null,
        has_data: false,
      }

      return json(route, { ok: true, symbol, name: stock.name })
    }

    if (request.method() === 'GET' && path.startsWith('/api/stocks/') && path.endsWith('/chart')) {
      const symbol = path.split('/')[3]
      const chart = state.charts[symbol]
      if (!chart) {
        return json(route, { detail: '该股票还没有可用历史数据，请先同步日线数据。' }, 404)
      }
      return json(route, chart)
    }

    if (request.method() === 'GET' && path.startsWith('/api/stocks/')) {
      const symbol = path.split('/')[3]
      const detail = state.stockDetails[symbol]
      if (!detail) {
        return json(route, { detail: '未找到该股票。' }, 404)
      }
      return json(route, detail)
    }

    if (request.method() === 'POST' && path === '/api/watchlist/sync') {
      return json(route, { ok: true, count: state.watchlistRows.length })
    }

    if (request.method() === 'POST' && path === '/api/reports') {
      return json(route, { ok: true, report_date: state.generatedReportDate })
    }

    if (request.method() === 'GET' && path === '/api/reports/latest') {
      if (!state.latestReportDate) {
        return json(route, { detail: '还没有可用日报。' }, 404)
      }
      return json(route, state.reportsByDate[state.latestReportDate])
    }

    if (request.method() === 'GET' && path.startsWith('/api/reports/')) {
      const reportDate = path.split('/')[3]
      const report = state.reportsByDate[reportDate]
      if (!report) {
        return json(route, { detail: '未找到该日报。' }, 404)
      }
      return json(route, report)
    }

    return json(route, { detail: `Unhandled mock route: ${request.method()} ${path}` }, 500)
  })
}

function parseRequestBody(rawBody: string | null): Record<string, unknown> {
  if (!rawBody) {
    return {}
  }

  try {
    return JSON.parse(rawBody) as Record<string, unknown>
  } catch {
    return {}
  }
}

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json; charset=utf-8',
    body: JSON.stringify(body),
  })
}

function svg(route: Route, label: string) {
  return route.fulfill({
    status: 200,
    contentType: 'image/svg+xml; charset=utf-8',
    body: `<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"><rect width="1280" height="720" fill="#f8fafc"/><rect x="40" y="40" width="1200" height="640" rx="24" fill="#ffffff" stroke="#cbd5e1"/><text x="80" y="120" font-size="42" fill="#0f172a">${label}</text><text x="80" y="180" font-size="26" fill="#475569">Mocked 涨停简图</text></svg>`,
  })
}
