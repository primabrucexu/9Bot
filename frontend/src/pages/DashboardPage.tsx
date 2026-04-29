import { type FormEvent, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { requestJson } from '../api/client'
import type {
  BaseStockPoolResponse,
  LimitUpCopyResponse,
  MarketDataSyncResponse,
  MarketOverviewResponse,
  MarketUniverseRefreshResponse,
} from '../api/types'

type StatusType = 'info' | 'success' | 'error'

type StatusBanner = {
  message: string
  type: StatusType
}

const PAGE_LIMIT = 50

function DashboardPage() {
  const navigate = useNavigate()
  const [stockPool, setStockPool] = useState<BaseStockPoolResponse | null>(null)
  const [keyword, setKeyword] = useState('')
  const [query, setQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const [status, setStatus] = useState<StatusBanner | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pendingAction, setPendingAction] = useState<string | null>(null)
  const [marketOverview, setMarketOverview] = useState<MarketOverviewResponse | null>(null)
  const [marketOverviewLoading, setMarketOverviewLoading] = useState(true)
  const [marketOverviewError, setMarketOverviewError] = useState<string | null>(null)
  const [limitUpCopy, setLimitUpCopy] = useState<LimitUpCopyResponse | null>(null)
  const [limitUpCopyLoading, setLimitUpCopyLoading] = useState(false)
  const [limitUpCopyError, setLimitUpCopyError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadStockPool() {
      setLoading(true)
      setError(null)

      try {
        const payload = await requestJson<BaseStockPoolResponse>(buildStockPoolPath(query, offset))
        if (!cancelled) {
          setStockPool(payload)
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(getErrorMessage(loadError))
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadStockPool()

    return () => {
      cancelled = true
    }
  }, [offset, query])

  useEffect(() => {
    let cancelled = false

    async function loadMarketOverview() {
      setMarketOverviewLoading(true)
      setMarketOverviewError(null)

      try {
        const payload = await requestJson<MarketOverviewResponse>('/market-overview')
        if (!cancelled) {
          setMarketOverview(payload)
        }
      } catch (loadError) {
        if (!cancelled) {
          setMarketOverviewError(getErrorMessage(loadError))
        }
      } finally {
        if (!cancelled) {
          setMarketOverviewLoading(false)
        }
      }
    }

    void loadMarketOverview()

    return () => {
      cancelled = true
    }
  }, [])

  const statusClassName = useMemo(() => {
    if (!status) {
      return 'status-banner hidden'
    }
    return `status-banner status-${status.type}`
  }, [status])

  async function handleRefreshUniverse() {
    try {
      setPendingAction('refresh-universe')
      setStatus({ message: '正在刷新全市场股票清单...', type: 'info' })
      const payload = await requestJson<MarketUniverseRefreshResponse>('/market-data/universe/refresh', {
        method: 'POST',
      })
      setStatus({ message: `全市场股票清单已刷新，共 ${payload.count} 只股票。`, type: 'success' })
    } catch (actionError) {
      setStatus({ message: getErrorMessage(actionError), type: 'error' })
    } finally {
      setPendingAction(null)
    }
  }

  async function handleSyncMarketData(historyDays: number) {
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
      setMarketOverviewLoading(true)
      const overview = await requestJson<MarketOverviewResponse>('/market-overview')
      setMarketOverview(overview)
      setMarketOverviewError(null)
    } catch (actionError) {
      setStatus({ message: getErrorMessage(actionError), type: 'error' })
    } finally {
      setMarketOverviewLoading(false)
      setPendingAction(null)
    }
  }

  async function handleRunLimitUpCopy() {
    try {
      setLimitUpCopyLoading(true)
      setLimitUpCopyError(null)
      const payload = await requestJson<LimitUpCopyResponse>('/stock-pool/limit-up-copy?limit=10')
      setLimitUpCopy(payload)
    } catch (loadError) {
      setLimitUpCopyError(getErrorMessage(loadError))
    } finally {
      setLimitUpCopyLoading(false)
    }
  }

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setOffset(0)
    setQuery(keyword.trim())
  }

  function handleReset() {
    setKeyword('')
    setOffset(0)
    setQuery('')
  }

  function openStockDetail(symbol: string) {
    navigate(`/stocks/${symbol}`)
  }

  if (loading) {
    return <LoadingPanel message="正在加载基础股票池..." />
  }

  if (error) {
    return (
      <section className="panel empty-state">
        <h2>加载失败</h2>
        <p>{error}</p>
        <button type="button" onClick={() => window.location.reload()}>
          重新加载
        </button>
      </section>
    )
  }

  const rows = stockPool?.rows ?? []
  const total = stockPool?.total ?? 0
  const hasPreviousPage = offset > 0
  const hasNextPage = stockPool !== null && offset + rows.length < total

  return (
    <>
      <section className="page-header">
        <div>
          <p className="eyebrow">全市场底座</p>
          <h1>A 股数据工作台</h1>
          <p className="subtle">先手动准备全市场数据底座，再从基础池与策略结果中查看个股详情。</p>
        </div>
        <Link className="text-link" to="/reports/latest">
          查看最新日报
        </Link>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>市场数据准备</h2>
            <p className="muted">首次同步会自动补齐全市场股票清单；默认建议先同步最近 30 天，再按需回补近 1 年。</p>
          </div>
          <div className="action-group">
            <button type="button" onClick={() => void handleRefreshUniverse()} disabled={pendingAction !== null}>
              {pendingAction === 'refresh-universe' ? '刷新中...' : '刷新全市场清单'}
            </button>
            <button type="button" onClick={() => void handleSyncMarketData(30)} disabled={pendingAction !== null}>
              {pendingAction === 'sync-30' ? '同步中...' : '同步近30天'}
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={() => void handleSyncMarketData(365)}
              disabled={pendingAction !== null}
            >
              {pendingAction === 'sync-365' ? '回补中...' : '回补近1年'}
            </button>
          </div>
        </div>
        <div className={statusClassName}>{status?.message}</div>
      </section>

      {marketOverviewLoading ? (
        <section className="panel empty-state compact-empty-state">
          <p>正在加载大盘数据...</p>
        </section>
      ) : marketOverviewError ? (
        <section className="panel empty-state compact-empty-state">
          <h2>大盘数据暂时不可用</h2>
          <p>{marketOverviewError}</p>
        </section>
      ) : marketOverview?.indices.length ? (
        <section className="metric-grid" aria-label="大盘概览">
          {marketOverview.indices.map((item) => (
            <article key={item.symbol} className="metric-card">
              <span>{item.name}</span>
              <strong>{formatNumber(item.summary.close)}</strong>
              <div className="signal-list compact-signal-list">
                <span className={`badge badge-soft ${getChangeClassName(item.summary.daily_change_pct) ?? ''}`.trim()}>
                  {formatPercent(item.summary.daily_change_pct)}
                </span>
                <span className="badge badge-soft">{item.summary.is_above_ma20 ? 'MA20 上方' : 'MA20 下方'}</span>
                <span className="badge badge-soft">MACD {item.summary.macd_bias}</span>
                <span className="badge badge-soft">{item.summary.trade_date}</span>
              </div>
            </article>
          ))}
        </section>
      ) : null}

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>涨停复制 Top10</h2>
            <p className="muted">按近 7 日涨停、近 10 日热点板块与技术形态综合打分，范围仅限沪深主板非 ST。</p>
          </div>
          <div className="action-group">
            <button type="button" onClick={() => void handleRunLimitUpCopy()} disabled={limitUpCopyLoading}>
              {limitUpCopyLoading ? '选股中...' : '运行选股'}
            </button>
          </div>
        </div>

        {limitUpCopyError ? (
          <div className="empty-state compact-empty-state">
            <h3>选股失败</h3>
            <p>{limitUpCopyError}</p>
          </div>
        ) : limitUpCopy === null ? (
          <div className="empty-state compact-empty-state">
            <h3>尚未运行选股</h3>
            <p>点击“运行选股”即可查看截至最新交易日收盘的 Top10 候选股。</p>
          </div>
        ) : (
          <>
            <div className="signal-list compact-signal-list">
              <span className="badge badge-soft">截止 {limitUpCopy.trade_date}</span>
              {limitUpCopy.hot_sectors.map((sector) => (
                <span key={sector.name} className="badge badge-soft">
                  热点 {sector.rank}: {sector.name} ({sector.count})
                </span>
              ))}
            </div>

            {limitUpCopy.rows.length === 0 ? (
              <div className="empty-state compact-empty-state">
                <h3>暂无结果</h3>
                <p>最新交易日没有满足条件的候选股。</p>
              </div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>代码</th>
                      <th>名称</th>
                      <th>板块</th>
                      <th>分数</th>
                      <th>最近涨停</th>
                      <th>最新涨跌幅</th>
                      <th>信号</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {limitUpCopy.rows.map((row) => (
                      <tr key={row.symbol}>
                        <td>{row.symbol}</td>
                        <td>{row.name}</td>
                        <td>{row.sector}</td>
                        <td>{row.score}</td>
                        <td>
                          {row.last_limit_up_date}
                          <br />
                          <span className="muted">{row.limit_up_count_7d} 次 / 最高 {row.max_board_count} 板</span>
                        </td>
                        <td className={getChangeClassName(row.daily_change_pct)}>{formatPercent(row.daily_change_pct)}</td>
                        <td>
                          <div className="signal-list compact-signal-list">
                            {row.signals.map((signal) => (
                              <span key={signal} className="badge badge-soft">
                                {signal}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td>
                          <button className="ghost-button" type="button" onClick={() => openStockDetail(row.symbol)}>
                            查看详情
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </section>

      <section className="panel controls-panel">
        <form className="inline-form" onSubmit={handleSearch}>
          <label htmlFor="stock-pool-search">搜索股票代码或名称</label>
          <div className="inline-form-row">
            <input
              id="stock-pool-search"
              placeholder="例如 600519 或 贵州茅台"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
            />
            <button type="submit">搜索</button>
            <button className="secondary-button" type="button" onClick={handleReset}>
              重置
            </button>
          </div>
        </form>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>基础筛选池</h2>
            <p className="muted">当前共 {total} 只，单页最多展示 {stockPool?.limit ?? PAGE_LIMIT} 只。</p>
          </div>
          <div className="action-group">
            <button
              className="secondary-button"
              type="button"
              disabled={!hasPreviousPage}
              onClick={() => setOffset((currentOffset) => Math.max(0, currentOffset - PAGE_LIMIT))}
            >
              上一页
            </button>
            <button
              className="secondary-button"
              type="button"
              disabled={!hasNextPage}
              onClick={() => setOffset((currentOffset) => currentOffset + PAGE_LIMIT)}
            >
              下一页
            </button>
          </div>
        </div>

        {rows.length === 0 ? (
          <div className="empty-state compact-empty-state">
            <h3>没有匹配结果</h3>
            <p>{query ? '换个代码或名称再试试。' : '当前没有可展示的股票。'}</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>代码</th>
                  <th>名称</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.symbol}>
                    <td>{row.symbol}</td>
                    <td>{row.name}</td>
                    <td>
                      <button className="ghost-button" type="button" onClick={() => openStockDetail(row.symbol)}>
                        查看详情
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}

function buildStockPoolPath(query: string, offset: number) {
  const params = new URLSearchParams({
    limit: String(PAGE_LIMIT),
    offset: String(offset),
  })
  if (query) {
    params.set('q', query)
  }
  return `/stock-pool/base?${params.toString()}`
}

function formatNumber(value: number | null): string {
  return value === null ? '--' : value.toFixed(2)
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

function LoadingPanel({ message }: { message: string }) {
  return (
    <section className="panel empty-state">
      <h2>请稍候</h2>
      <p>{message}</p>
    </section>
  )
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message
  }
  return '请求失败'
}

export default DashboardPage
