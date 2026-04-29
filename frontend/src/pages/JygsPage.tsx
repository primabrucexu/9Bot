import { useEffect, useMemo, useState } from 'react'
import { requestJson } from '../api/client'
import type { JygsFetchResponse, JygsLoginActionResponse, JygsStatusResponse } from '../api/types'

type StatusType = 'info' | 'success' | 'error'

type StatusBanner = {
  message: string
  type: StatusType
}

const ACTIVE_LOGIN_FLOW_STATUSES = new Set(['starting', 'waiting', 'saving'])

function JygsPage() {
  const [status, setStatus] = useState<JygsStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [banner, setBanner] = useState<StatusBanner | null>(null)
  const [startingLogin, setStartingLogin] = useState(false)
  const [completingLogin, setCompletingLogin] = useState(false)
  const [fetchingDiagram, setFetchingDiagram] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function loadStatus() {
      setLoading(true)
      setError(null)
      try {
        const payload = await requestJson<JygsStatusResponse>('/jygs/status')
        if (!cancelled) {
          setStatus(payload)
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

    void loadStatus()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!status || !ACTIVE_LOGIN_FLOW_STATUSES.has(status.login_flow.status)) {
      return undefined
    }

    const timer = window.setInterval(() => {
      void refreshStatus(true)
    }, 2000)

    return () => {
      window.clearInterval(timer)
    }
  }, [status])

  const bannerClassName = useMemo(() => {
    if (!banner) {
      return 'status-banner hidden'
    }
    return `status-banner status-${banner.type}`
  }, [banner])

  const loginFlowStatus = status?.login_flow.status ?? 'idle'
  const loginBusy = startingLogin || completingLogin || ACTIVE_LOGIN_FLOW_STATUSES.has(loginFlowStatus)
  const fetchDisabled = !status?.login_ready || fetchingDiagram || loginBusy

  async function refreshStatus(silent = false) {
    if (!silent) {
      setLoading(true)
      setError(null)
    }

    try {
      const payload = await requestJson<JygsStatusResponse>('/jygs/status')
      setStatus(payload)
      if (!silent) {
        setBanner({ message: '已刷新韭研公社状态。', type: 'success' })
      }
    } catch (loadError) {
      if (!silent) {
        setError(getErrorMessage(loadError))
      }
    } finally {
      if (!silent) {
        setLoading(false)
      }
    }
  }

  async function handleStartLogin() {
    try {
      setStartingLogin(true)
      setBanner({ message: '正在启动 Edge 登录窗口...', type: 'info' })
      const payload = await requestJson<JygsLoginActionResponse>('/jygs/login/start', {
        method: 'POST',
      })
      setStatus(payload.status)
      setBanner({
        message: payload.status.login_flow.message ?? '已打开登录窗口，请在 Edge 中完成登录。',
        type: 'info',
      })
    } catch (actionError) {
      setBanner({ message: getErrorMessage(actionError), type: 'error' })
    } finally {
      setStartingLogin(false)
    }
  }

  async function handleCompleteLogin() {
    try {
      setCompletingLogin(true)
      setBanner({ message: '正在保存登录态，请稍候...', type: 'info' })
      const payload = await requestJson<JygsLoginActionResponse>('/jygs/login/complete', {
        method: 'POST',
      })
      setStatus(payload.status)
      setBanner({
        message: payload.status.login_ready
          ? '登录态已保存，可以开始抓取最新涨停简图。'
          : payload.status.login_flow.message ?? '登录流程尚未完成。',
        type: payload.status.login_ready ? 'success' : 'info',
      })
    } catch (actionError) {
      setBanner({ message: getErrorMessage(actionError), type: 'error' })
    } finally {
      setCompletingLogin(false)
    }
  }

  async function handleFetchDiagram() {
    try {
      setFetchingDiagram(true)
      setBanner({ message: '正在抓取最新涨停简图...', type: 'info' })
      const payload = await requestJson<JygsFetchResponse>('/jygs/diagram/fetch', {
        method: 'POST',
      })
      setStatus(payload.status)
      setBanner({
        message:
          payload.skipped.length > 0
            ? '最新交易日简图已存在，已直接返回本地结果。'
            : '最新交易日涨停简图抓取完成。',
        type: 'success',
      })
    } catch (actionError) {
      setBanner({ message: getErrorMessage(actionError), type: 'error' })
    } finally {
      setFetchingDiagram(false)
    }
  }

  if (loading) {
    return (
      <section className="panel empty-state">
        <h2>请稍候</h2>
        <p>正在加载韭研公社状态...</p>
      </section>
    )
  }

  if (error || !status) {
    return (
      <section className="panel empty-state">
        <h2>加载失败</h2>
        <p>{error ?? '未获取到韭研公社状态。'}</p>
        <button type="button" onClick={() => void refreshStatus()}>
          重新加载
        </button>
      </section>
    )
  }

  return (
    <>
      <section className="page-header">
        <div>
          <p className="eyebrow">韭研公社</p>
          <h1>涨停简图工作台</h1>
          <p className="subtle">
            通过网页按钮拉起本机 Edge 登录韭研公社，保存本地登录态后抓取最新交易日的涨停简图。
          </p>
        </div>
      </section>

      <section className="panel controls-panel">
        <div className={bannerClassName}>{banner?.message}</div>
      </section>

      <div className="jygs-layout">
        <section className="panel side-panel">
          <div className="panel-header">
            <div>
              <h2>网页登录</h2>
              <p className="muted">登录在本机 Edge 中完成，系统只保存登录后的会话态，不保存账号密码。</p>
            </div>
            <div className="action-group">
              <button type="button" onClick={() => void handleStartLogin()} disabled={startingLogin || completingLogin}>
                {startingLogin ? '启动中...' : '启动登录'}
              </button>
              <button
                className="secondary-button"
                type="button"
                onClick={() => void handleCompleteLogin()}
                disabled={completingLogin || loginFlowStatus === 'idle'}
              >
                {completingLogin ? '保存中...' : '我已登录，保存登录态'}
              </button>
              <button className="ghost-button" type="button" onClick={() => void refreshStatus()} disabled={loading}>
                刷新状态
              </button>
            </div>
          </div>

          <div className="signal-list compact-signal-list">
            <span className="badge badge-soft">登录态：{status.login_ready ? '已就绪' : '未就绪'}</span>
            <span className="badge badge-soft">流程：{formatLoginFlow(status.login_flow.status)}</span>
          </div>

          <div className="jygs-meta-list">
            <div>
              <strong>当前提示</strong>
              <p>{status.login_flow.message ?? '点击“启动登录”后会自动打开本机 Edge 登录页。'}</p>
            </div>
            <div>
              <strong>登录态文件</strong>
              <p>{status.storage_state_path}</p>
            </div>
            {status.login_flow.login_url ? (
              <div>
                <strong>登录页面</strong>
                <p>
                  <a href={status.login_flow.login_url} target="_blank" rel="noreferrer">
                    {status.login_flow.login_url}
                  </a>
                </p>
              </div>
            ) : null}
          </div>

          <ol className="helper-list">
            <li>点击“启动登录”，系统会为你打开本机 Edge 登录窗口。</li>
            <li>在弹出的 Edge 中完成韭研公社登录，并确认页面已正常打开。</li>
            <li>回到这里点击“我已登录，保存登录态”，系统会落盘本地会话态。</li>
            <li>登录态准备完成后，再点击“抓取最新简图”。</li>
          </ol>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>最新涨停简图</h2>
              <p className="muted">当前先支持抓取最新交易日简图，并展示本地图片结果。</p>
            </div>
            <div className="action-group">
              <button type="button" onClick={() => void handleFetchDiagram()} disabled={fetchDisabled}>
                {fetchingDiagram ? '抓取中...' : '抓取最新简图'}
              </button>
            </div>
          </div>

          {!status.login_ready ? (
            <div className="empty-state compact-empty-state">
              <h3>还没有可用登录态</h3>
              <p>请先完成网页登录并保存登录态，之后才能抓取韭研公社简图。</p>
            </div>
          ) : status.latest === null ? (
            <div className="empty-state compact-empty-state">
              <h3>还没有本地简图</h3>
              <p>登录态已就绪，可以直接点击“抓取最新简图”获取今天最近一个交易日的图片。</p>
            </div>
          ) : (
            <div className="diagram-preview">
              <div className="signal-list compact-signal-list">
                <span className="badge badge-soft">日期 {status.latest.date}</span>
                <span className="badge badge-soft">状态 {status.latest.status}</span>
                {status.latest.updated_at ? (
                  <span className="badge badge-soft">更新于 {formatDateTime(status.latest.updated_at)}</span>
                ) : null}
              </div>
              <img
                className="diagram-image"
                src={status.latest.image_url}
                alt={`韭研公社 ${status.latest.date} 涨停简图`}
              />
              <div className="action-group">
                <a href={status.latest.image_url} target="_blank" rel="noreferrer">
                  在新窗口查看本地图
                </a>
                {status.latest.source_image_url ? (
                  <a href={status.latest.source_image_url} target="_blank" rel="noreferrer">
                    查看原始图片地址
                  </a>
                ) : null}
              </div>
            </div>
          )}
        </section>
      </div>
    </>
  )
}

function formatLoginFlow(status: string) {
  switch (status) {
    case 'starting':
      return '启动中'
    case 'waiting':
      return '等待登录'
    case 'saving':
      return '保存中'
    case 'saved':
      return '已保存'
    case 'failed':
      return '失败'
    default:
      return '未开始'
  }
}

function formatDateTime(value: string) {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleString('zh-CN', { hour12: false })
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message
  }
  return '请求失败'
}

export default JygsPage
