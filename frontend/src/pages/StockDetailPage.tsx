import { type RefObject, useEffect, useMemo, useRef, useState } from 'react'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import { Link, useParams } from 'react-router-dom'
import { requestJson } from '../api/client'
import type { ChartPayload, StockDetailResponse } from '../api/types'

function StockDetailPage() {
  const { symbol = '' } = useParams()
  const [detail, setDetail] = useState<StockDetailResponse | null>(null)
  const [chartData, setChartData] = useState<ChartPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [chartError, setChartError] = useState<string | null>(null)

  const priceChartRef = useRef<HTMLDivElement | null>(null)
  const macdChartRef = useRef<HTMLDivElement | null>(null)
  const rsiChartRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadStockDetail() {
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

    void loadStockDetail()

    return () => {
      cancelled = true
    }
  }, [symbol])

  const priceOption = useMemo(() => (chartData ? buildPriceChartOption(chartData) : null), [chartData])
  const macdOption = useMemo(() => (chartData ? buildMacdChartOption(chartData) : null), [chartData])
  const rsiOption = useMemo(() => (chartData ? buildRsiChartOption(chartData) : null), [chartData])

  useChart(priceChartRef, priceOption)
  useChart(macdChartRef, macdOption)
  useChart(rsiChartRef, rsiOption)

  if (loading) {
    return (
      <section className="panel empty-state">
        <h2>请稍候</h2>
        <p>正在加载个股详情...</p>
      </section>
    )
  }

  if (error || !detail) {
    return (
      <section className="panel empty-state">
        <h2>加载失败</h2>
        <p>{error ?? '未找到该股票。'}</p>
        <Link className="text-link" to="/">
          返回看板
        </Link>
      </section>
    )
  }

  const { stock, summary } = detail

  return (
    <>
      <section className="page-header detail-header">
        <div>
          <p className="eyebrow">个股详情</p>
          <h1>
            {stock.name} <span className="muted">{stock.symbol}</span>
          </h1>
          <p className="subtle">日线、均线、MACD、RSI 与规则型结论。</p>
        </div>
        <Link className="text-link" to="/">
          返回看板
        </Link>
      </section>

      {summary ? (
        <>
          <section className="metric-grid">
            <article className="metric-card">
              <span>最新收盘</span>
              <strong>{summary.close.toFixed(2)}</strong>
            </article>
            <article className="metric-card">
              <span>涨跌幅</span>
              <strong className={getChangeClassName(summary.daily_change_pct)}>
                {formatPercent(summary.daily_change_pct)}
              </strong>
            </article>
            <article className="metric-card">
              <span>MA20 位置</span>
              <strong>{summary.is_above_ma20 ? '上方' : '下方'}</strong>
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
          <h2>还没有行情数据</h2>
          <p>先回到看板页刷新一次行情，再来看这只股票的 K 线与指标。</p>
        </section>
      )}
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

function getChangeClassName(value: number | null): string | undefined {
  if (value === null || value === 0) {
    return undefined
  }
  return value > 0 ? 'positive' : 'negative'
}

function formatPercent(value: number | null): string {
  return value === null ? '--' : `${value.toFixed(2)}%`
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message
  }
  return '请求失败'
}

export default StockDetailPage
