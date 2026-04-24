import { type FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { requestJson } from '../api/client'
import type {
  DashboardResponse,
  RefreshWatchlistResponse,
  ReportGenerationResponse,
  WatchlistMutationResponse,
} from '../api/types'

type StatusType = 'info' | 'success' | 'error'

type StatusBanner = {
  message: string
  type: StatusType
}

function DashboardPage() {
  const navigate = useNavigate()
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null)
  const [symbol, setSymbol] = useState('')
  const [status, setStatus] = useState<StatusBanner | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pendingAction, setPendingAction] = useState<string | null>(null)

  const loadDashboard = useCallback(async () => {
    setError(null)
    const payload = await requestJson<DashboardResponse>('/dashboard')
    setDashboard(payload)
  }, [])

  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      setLoading(true)
      try {
        const payload = await requestJson<DashboardResponse>('/dashboard')
        if (!cancelled) {
          setDashboard(payload)
          setError(null)
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

    void bootstrap()

    return () => {
      cancelled = true
    }
  }, [])

  const rows = dashboard?.rows ?? []
  const isBusy = pendingAction !== null
  const statusClassName = useMemo(() => {
    if (!status) {
      return 'status-banner hidden'
    }
    return `status-banner status-${status.type}`
  }, [status])

  async function reloadDashboardAfterAction(successMessage?: string) {
    await loadDashboard()
    setLoading(false)
    if (successMessage) {
      setStatus({ message: successMessage, type: 'success' })
    }
  }

  async function handleAddWatchlist(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalized = symbol.trim()
    if (!normalized) {
      setStatus({ message: '请输入股票代码。', type: 'error' })
      return
    }

    try {
      setPendingAction('add')
      setStatus({ message: '正在添加自选股...', type: 'info' })
      const payload = await requestJson<WatchlistMutationResponse>('/watchlist', {
        method: 'POST',
        body: JSON.stringify({ symbol: normalized }),
      })
      setSymbol('')
      await reloadDashboardAfterAction(`已加入 ${payload.name ?? normalized}。`)
    } catch (actionError) {
      setStatus({ message: getErrorMessage(actionError), type: 'error' })
    } finally {
      setPendingAction(null)
    }
  }

  async function handleRefresh() {
    try {
      setPendingAction('refresh')
      setStatus({ message: '正在刷新行情，请稍候...', type: 'info' })
      const payload = await requestJson<RefreshWatchlistResponse>('/watchlist/refresh', {
        method: 'POST',
      })
      await reloadDashboardAfterAction(`刷新完成，共更新 ${payload.count} 只股票。`)
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
      navigate(`/reports/${payload.report_date}`)
    } catch (actionError) {
      setStatus({ message: getErrorMessage(actionError), type: 'error' })
    } finally {
      setPendingAction(null)
    }
  }

  async function handleDelete(symbolToDelete: string) {
    try {
      setPendingAction(`delete:${symbolToDelete}`)
      setStatus({ message: `正在删除 ${symbolToDelete}...`, type: 'info' })
      await requestJson<WatchlistMutationResponse>(`/watchlist/${symbolToDelete}`, {
        method: 'DELETE',
      })
      await reloadDashboardAfterAction(`已删除 ${symbolToDelete}。`)
    } catch (actionError) {
      setStatus({ message: getErrorMessage(actionError), type: 'error' })
    } finally {
      setPendingAction(null)
    }
  }

  if (loading && !dashboard) {
    return <LoadingPanel message="正在加载看板数据..." />
  }

  if (error && !dashboard) {
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

  return (
    <>
      <section className="page-header">
        <div>
          <p className="eyebrow">自选股看板</p>
          <h1>本地 A 股分析工作台</h1>
          <p className="subtle">先维护你的自选股，再手动刷新行情和生成 AI 日报。</p>
        </div>
      </section>

      <section className="panel controls-panel">
        <div className="controls-grid">
          <form className="inline-form" onSubmit={handleAddWatchlist}>
            <label htmlFor="symbol-input">添加股票代码</label>
            <div className="inline-form-row">
              <input
                id="symbol-input"
                maxLength={6}
                inputMode="numeric"
                placeholder="例如 600519"
                required
                value={symbol}
                onChange={(event) => setSymbol(event.target.value)}
              />
              <button type="submit" disabled={isBusy}>
                {pendingAction === 'add' ? '处理中...' : '加入自选'}
              </button>
            </div>
          </form>
          <div className="action-group">
            <button type="button" onClick={handleRefresh} disabled={isBusy}>
              {pendingAction === 'refresh' ? '刷新中...' : '刷新行情'}
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={handleGenerateReport}
              disabled={isBusy}
            >
              {pendingAction === 'report' ? '生成中...' : '生成 AI 日报'}
            </button>
          </div>
        </div>
        <div className={statusClassName}>{status?.message}</div>
      </section>

      <section className="content-grid">
        <div className="panel">
          <div className="panel-header">
            <h2>自选股</h2>
            <span className="muted">{rows.length} 只</span>
          </div>
          {rows.length > 0 ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>代码</th>
                    <th>名称</th>
                    <th>最新价</th>
                    <th>涨跌幅</th>
                    <th>MA20</th>
                    <th>MACD</th>
                    <th>RSI</th>
                    <th>最近交易日</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <DashboardRowItem
                      key={row.symbol}
                      isBusy={isBusy}
                      isDeleting={pendingAction === `delete:${row.symbol}`}
                      onDelete={handleDelete}
                      row={row}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">
              <h3>还没有自选股</h3>
              <p>先输入一个 6 位股票代码开始，例如 600519 或 000001。</p>
            </div>
          )}
        </div>

        <aside className="panel side-panel">
          <div className="panel-header">
            <h2>最近日报</h2>
          </div>
          {dashboard?.latest_report ? (
            <>
              <p className="muted">{dashboard.latest_report.report_date}</p>
              <pre className="report-preview">{dashboard.latest_report.preview_markdown}</pre>
              <Link className="text-link" to={`/reports/${dashboard.latest_report.report_date}`}>
                查看完整日报
              </Link>
            </>
          ) : (
            <div className="empty-state compact-empty-state">
              <p>还没有日报。先刷新行情，再点击“生成 AI 日报”。</p>
            </div>
          )}
        </aside>
      </section>
    </>
  )
}

type DashboardRowItemProps = {
  row: DashboardResponse['rows'][number]
  isBusy: boolean
  isDeleting: boolean
  onDelete: (symbol: string) => Promise<void>
}

function DashboardRowItem({ row, isBusy, isDeleting, onDelete }: DashboardRowItemProps) {
  return (
    <>
      <tr>
        <td>
          <Link to={`/stocks/${row.symbol}`}>{row.symbol}</Link>
        </td>
        <td>{row.name}</td>
        <td>{formatNumber(row.latest_close)}</td>
        <td className={getChangeClassName(row.daily_change_pct)}>{formatPercent(row.daily_change_pct)}</td>
        <td>
          <span className="badge">{row.ma_status}</span>
        </td>
        <td>{row.macd_bias}</td>
        <td>{row.rsi_state}</td>
        <td>{row.last_trade_date ?? '--'}</td>
        <td>
          <button
            className="ghost-button"
            type="button"
            onClick={() => void onDelete(row.symbol)}
            disabled={isBusy}
          >
            {isDeleting ? '删除中...' : '删除'}
          </button>
        </td>
      </tr>
      {row.signals.length > 0 ? (
        <tr className="signal-row">
          <td colSpan={9}>
            <div className="signal-list">
              {row.signals.map((signal) => (
                <span key={`${row.symbol}-${signal}`} className="badge badge-soft">
                  {signal}
                </span>
              ))}
            </div>
          </td>
        </tr>
      ) : null}
    </>
  )
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

export default DashboardPage
