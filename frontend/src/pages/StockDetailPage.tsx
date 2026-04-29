import { type FormEvent, type RefObject, useEffect, useMemo, useRef, useState } from 'react'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { requestJson } from '../api/client'
import type { ChartPayload, MarketDataSyncResponse, ReportGenerationResponse, StockDetailResponse } from '../api/types'

type StatusType = 'info' | 'success' | 'error'

type StatusBanner = {
  message: string
  type: StatusType
}

function StockDetailPage() {
  const navigate = useNavigate()
  const { symbol = '' } = useParams()
  const [detail, setDetail] = useState<StockDetailResponse | null>(null)
  const [chartData, setChartData] = useState<ChartPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [chartError, setChartError] = useState<string | null>(null)
  const [status, setStatus] = useState<StatusBanner | null>(null)
  const [pendingAction, setPendingAction] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  const priceChartRef = useRef<HTMLDivElement | null>(null)
  const macdChartRef = useRef<HTMLDivElement | null>(null)
  const rsiChartRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadPage() {
      if (!symbol) {
        setLoading(false)
        setDetail(null)
        setError('缺少股票代码。')
        return
      }

      setLoading(true)
      setError(null)
      setChartError(null)
      setChartData(null)

      try {
        const stockDetail = await requestJson<StockDetailResponse>(`/stocks/${symbol}`)
        if (cancelled) {
          return
        }
        setDetail(stockDetail)

        if (!stockDetail.has_data) {
          return
        }

        try {
          const payload = await requestJson<ChartPayload>(`/stocks/${symbol}/chart`)
          if (!cancelled) {
            setChartData(payload)
          }
        } catch (loadError) {
          if (!cancelled) {
            setChartError(getErrorMessage(loadError))
          }
        }
      } catch (loadError) {
        if (!cancelled) {
          setDetail(null)
          setError(getErrorMessage(loadError))
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadPage()

    return () => {
      cancelled = true
    }
  }, [reloadKey, symbol])

  const priceOption = useMemo(() => (chartData ? buildPriceChartOption(chartData) : null), [chartData])
  const macdOption = useMemo(() => (chartData ? buildMacdChartOption(chartData) : null), [chartData])
  const rsiOption = useMemo(() => (chartData ? buildRsiChartOption(chartData) : null), [chartData])
  const statusClassName = useMemo(() => {
    if (!status) {
      return 'status-banner hidden'
    }
    return `status-banner status-${status.type}`
  }, [status])

  useChart(priceChartRef, priceOption)
  useChart(macdChartRef, macdOption)
  useChart(rsiChartRef, rsiOption)

  const isBusy = pendingAction !== null

  async function handleOpenSymbol(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const formData = new FormData(event.currentTarget)
    const normalized = String(formData.get('symbol') ?? '').trim()
    if (!normalized) {
      setStatus({ message: '请输入股票代码。', type: 'error' })
      return
    }
    navigate(`/stocks/${normalized}`)
  }

  async function handleSync(historyDays: number) {
    try {
      setPendingAction(`sync-${historyDays}`)
      setStatus({ message: `正在同步最近 ${historyDays} 天的市场日线数据...`, type: 'info' })
      const payload = await requestJson<MarketDataSyncResponse>('/market-data/sync', {
        method: 'POST',
        body: JSON.stringify({ history_days: historyDays }),
      })
      const tradeDateText = payload.last_trade_date ? `，最新交易日 ${payload.last_trade_date}` : ''
      setStatus({
        message: `同步完成，已更新 ${payload.synced_count}/${payload.universe_count} 只股票${tradeDateText}。`,
        type: 'success',
      })
      setReloadKey((value) => value + 1)
    } catch (actionError) {
      setStatus({ message: getErrorMessage(actionError), type: 'error' })
    } finally {
      setPendingAction(null)
    }
  }

  async function handleGenerateReport() {
    try {
      setPendingAction('report')
      setStatus({ message: '正在生成 AI 日报，请稍候...', type: 'info' })
      const payload = await requestJson<ReportGenerationResponse>('/reports', {
        method: 'POST',
      })
      setStatus({ message: `已生成 ${payload.report_date} 的日报。`, type: 'success' })
      navigate(`/reports/${payload.report_date}`)
    } catch (actionError) {
      setStatus({ message: getErrorMessage(actionError), type: 'error' })
    } finally {
      setPendingAction(null)
    }
  }

  if (loading) {
    return (
      <section className="panel empty-state">
        <h2>请稍候</h2>
        <p>正在加载股票详情...</p>
      </section>
    )
  }

  if (error) {
    return (
      <section className="panel empty-state">
        <h2>加载失败</h2>
        <p>{error}</p>
        <Link className="text-link" to="/">
          返回股票页
        </Link>
      </section>
    )
  }

  if (!detail) {
    return (
      <section className="panel empty-state">
        <h2>未找到该股票</h2>
        <p>请检查代码，或先返回工作台刷新全市场清单后重试。</p>
        <Link className="text-link" to="/">
          返回股票页
        </Link>
      </section>
    )
  }

  const { stock, summary } = detail

  return (
    <>
      <section className="page-header detail-header">
        <div>
          <p className="eyebrow">日线详情</p>
          <h1>
            {stock.name} <span className="muted">{stock.symbol}</span>
          </h1>
          <div className="signal-list compact-signal-list">
            {stock.market ? <span className="badge badge-soft">{stock.market}</span> : null}
            {stock.board ? <span className="badge badge-soft">{stock.board}</span> : null}
            {stock.is_st ? <span className="badge badge-soft">ST</span> : null}
            {stock.created_at ? <span className="badge badge-soft">加入时间 {stock.created_at.slice(0, 10)}</span> : null}
          </div>
          <p className="subtle">按股票代码直接查看本地缓存的日线 K 线、均线、MACD、RSI 与规则型结论。</p>
        </div>
        <div className="action-group">
          <Link className="text-link" to="/">
            返回工作台
          </Link>
          <Link className="text-link" to="/reports/latest">
            查看最新日报
          </Link>
        </div>
      </section>

      <div className={statusClassName}>{status?.message}</div>

      <section className="detail-layout">
        <aside className="panel stock-sidebar">
          <div className="panel-header">
            <h2>打开股票</h2>
          </div>

          <form className="inline-form" onSubmit={handleOpenSymbol}>
            <label htmlFor="detail-symbol-input">股票代码</label>
            <div className="inline-form-row">
              <input
                key={symbol}
                id="detail-symbol-input"
                name="symbol"
                maxLength={6}
                inputMode="numeric"
                placeholder="例如 600519"
                required
                defaultValue={symbol}
              />
              <button type="submit" disabled={isBusy}>
                打开
              </button>
            </div>
          </form>

          <section className="panel compact-panel">
            <div className="panel-header">
              <h3>市场数据操作</h3>
            </div>
            <p className="muted">如果当前股票没有本地日线，可先同步近 30 天，再按需回补近 1 年。</p>
            <div className="sidebar-actions">
              <button type="button" onClick={() => void handleSync(30)} disabled={isBusy}>
                {pendingAction === 'sync-30' ? '同步中...' : '同步近30天市场日线'}
              </button>
              <button
                type="button"
                className="secondary-button"
                onClick={() => void handleSync(365)}
                disabled={isBusy}
              >
                {pendingAction === 'sync-365' ? '回补中...' : '回补近1年市场日线'}
              </button>
              <button
                type="button"
                className="ghost-button"
                onClick={handleGenerateReport}
                disabled={isBusy}
              >
                {pendingAction === 'report' ? '生成中...' : '生成 AI 日报'}
              </button>
            </div>
          </section>
        </aside>

        <div className="detail-main">
          {summary ? (
            <>
              <section className="metric-grid">
                <article className="metric-card">
                  <span>最新收盘</span>
                  <strong>{summary.close.toFixed(2)}</strong>
                </article>
                <article className="metric-card">
                  <span>日涨跌幅</span>
                  <strong className={getChangeClassName(summary.daily_change_pct)}>
                    {formatPercent(summary.daily_change_pct)}
                  </strong>
                </article>
                <article className="metric-card">
                  <span>MA20 位置</span>
                  <strong>{summary.is_above_ma20 ? '上方' : '下方'}</strong>
                </article>
                <article className="metric-card">
                  <span>MACD</span>
                  <strong>{summary.macd_bias}</strong>
                </article>
                <article className="metric-card">
                  <span>RSI</span>
                  <strong>
                    {summary.rsi14 === null ? '--' : summary.rsi14.toFixed(2)} / {summary.rsi_state}
                  </strong>
                </article>
                <article className="metric-card">
                  <span>最近交易日</span>
                  <strong>{summary.trade_date}</strong>
                </article>
              </section>

              <section className="panel">
                <div className="panel-header">
                  <h2>规则型结论</h2>
                </div>
                <div className="signal-list">
                  {summary.signals.map((signal) => (
                    <span key={signal} className="badge badge-soft">
                      {signal}
                    </span>
                  ))}
                </div>
              </section>

              <section className="panel">
                <div className="panel-header">
                  <h2>K 线与成交量</h2>
                </div>
                {chartError ? (
                  <div className="chart large-chart chart-error">{chartError}</div>
                ) : (
                  <div ref={priceChartRef} className="chart large-chart"></div>
                )}
              </section>

              <section className="chart-columns">
                <section className="panel">
                  <div className="panel-header">
                    <h2>MACD</h2>
                  </div>
                  {chartError ? (
                    <div className="chart small-chart chart-error">{chartError}</div>
                  ) : (
                    <div ref={macdChartRef} className="chart small-chart"></div>
                  )}
                </section>
                <section className="panel">
                  <div className="panel-header">
                    <h2>RSI(14)</h2>
                  </div>
                  {chartError ? (
                    <div className="chart small-chart chart-error">{chartError}</div>
                  ) : (
                    <div ref={rsiChartRef} className="chart small-chart"></div>
                  )}
                </section>
              </section>
            </>
          ) : (
            <section className="panel empty-state">
              <h2>还没有日线数据</h2>
              <p>这只股票还没有本地日线数据。先同步最近 30 天的市场日线，再回来查看 K 线与指标。</p>
              <div className="action-group">
                <button type="button" onClick={() => void handleSync(30)} disabled={isBusy}>
                  {pendingAction === 'sync-30' ? '同步中...' : '立即同步近30天市场日线'}
                </button>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => void handleSync(365)}
                  disabled={isBusy}
                >
                  {pendingAction === 'sync-365' ? '回补中...' : '立即回补近1年市场日线'}
                </button>
              </div>
            </section>
          )}
        </div>
      </section>
    </>
  )
}

function useChart(containerRef: RefObject<HTMLDivElement | null>, option: EChartsOption | null) {
  useEffect(() => {
    const element = containerRef.current
    if (!element || !option) {
      return
    }

    const chart = echarts.init(element)
    chart.setOption(option)

    const resize = () => chart.resize()
    window.addEventListener('resize', resize)

    return () => {
      window.removeEventListener('resize', resize)
      chart.dispose()
    }
  }, [containerRef, option])
}

function buildVolumeSeries(data: ChartPayload) {
  return data.volume.map((value, index) => {
    const candle = data.candles[index]
    const open = candle?.[0] ?? 0
    const close = candle?.[1] ?? 0

    return {
      value,
      itemStyle: {
        color: close >= open ? '#ef4444' : '#16a34a',
      },
    }
  })
}

function buildPriceChartOption(data: ChartPayload): EChartsOption {
  return {
    animation: false,
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['K线', 'MA5', 'MA10', 'MA20', 'MA60', '成交量'] },
    grid: [
      { left: 48, right: 24, top: 42, height: '56%' },
      { left: 48, right: 24, top: '72%', height: '14%' },
    ],
    xAxis: [
      { type: 'category', data: data.dates, boundaryGap: false, axisLine: { onZero: false } },
      {
        type: 'category',
        gridIndex: 1,
        data: data.dates,
        boundaryGap: false,
        axisLabel: { show: false },
        axisTick: { show: false },
      },
    ],
    yAxis: [{ scale: true, splitArea: { show: true } }, { gridIndex: 1, scale: true, splitNumber: 2 }],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 60, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], top: '90%', start: 60, end: 100 },
    ],
    series: [
      { name: 'K线', type: 'candlestick', data: data.candles },
      { name: 'MA5', type: 'line', data: data.ma5, smooth: true, showSymbol: false, lineStyle: { width: 1 } },
      { name: 'MA10', type: 'line', data: data.ma10, smooth: true, showSymbol: false, lineStyle: { width: 1 } },
      { name: 'MA20', type: 'line', data: data.ma20, smooth: true, showSymbol: false, lineStyle: { width: 1 } },
      { name: 'MA60', type: 'line', data: data.ma60, smooth: true, showSymbol: false, lineStyle: { width: 1 } },
      { name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: buildVolumeSeries(data) },
    ],
  }
}

function buildMacdChartOption(data: ChartPayload): EChartsOption {
  return {
    animation: false,
    tooltip: { trigger: 'axis' },
    legend: { data: ['MACD', 'Signal', 'Histogram'] },
    xAxis: { type: 'category', data: data.dates, boundaryGap: false },
    yAxis: { scale: true },
    dataZoom: [{ type: 'inside', start: 60, end: 100 }],
    series: [
      {
        name: 'Histogram',
        type: 'bar',
        data: data.macd_hist.map((value) => ({
          value,
          itemStyle: { color: (value ?? 0) >= 0 ? '#ef4444' : '#16a34a' },
        })),
      },
      { name: 'MACD', type: 'line', data: data.macd, showSymbol: false },
      { name: 'Signal', type: 'line', data: data.macd_signal, showSymbol: false },
    ],
  }
}

function buildRsiChartOption(data: ChartPayload): EChartsOption {
  return {
    animation: false,
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: data.dates, boundaryGap: false },
    yAxis: { min: 0, max: 100 },
    dataZoom: [{ type: 'inside', start: 60, end: 100 }],
    series: [
      {
        name: 'RSI14',
        type: 'line',
        data: data.rsi14,
        showSymbol: false,
        markLine: {
          symbol: 'none',
          label: { formatter: '{b}' },
          data: [
            { yAxis: 70, name: '70' },
            { yAxis: 30, name: '30' },
          ],
        },
      },
    ],
  }
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message
  }
  return '请求失败'
}

function formatPercent(value: number | null): string {
  return value === null ? '--' : `${value.toFixed(2)}%`
}

function getChangeClassName(value: number | null): string | undefined {
  if (value === null || value === 0) {
    return undefined
  }
  return value > 0 ? 'positive' : 'negative'
}

export default StockDetailPage
