import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { requestJson } from '../api/client'
import type { ReportResponse } from '../api/types'

type ReportPageProps = {
  mode: 'latest' | 'byDate'
}

function ReportPage({ mode }: ReportPageProps) {
  const { reportDate } = useParams()
  const [report, setReport] = useState<ReportResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadReport() {
      setLoading(true)
      setError(null)

      try {
        const path = mode === 'latest' ? '/reports/latest' : `/reports/${reportDate}`
        const payload = await requestJson<ReportResponse>(path)
        if (!cancelled) {
          setReport(payload)
        }
      } catch (loadError) {
        if (!cancelled) {
          setReport(null)
          setError(getErrorMessage(loadError))
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadReport()

    return () => {
      cancelled = true
    }
  }, [mode, reportDate])

  const title = report ? `${report.report_date} 市场观察日报` : '还没有日报'

  return (
    <>
      <section className="page-header">
        <div>
          <p className="eyebrow">AI 日报</p>
          <h1>{title}</h1>
          <p className="subtle">日报基于本地缓存的日线数据和技术指标生成。</p>
        </div>
        <Link className="text-link" to="/">
          返回股票页
        </Link>
      </section>

      <section className="panel">
        {loading ? (
          <div className="empty-state compact-empty-state">
            <p>正在加载日报...</p>
          </div>
        ) : report ? (
          <>
            <p className="muted">模型：{report.model_name}</p>
            <pre className="report-body">{report.report_markdown}</pre>
          </>
        ) : (
          <div className="empty-state compact-empty-state">
            <p>{error ?? '当前还没有可展示的日报。'}</p>
          </div>
        )}
      </section>
    </>
  )
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message
  }
  return '请求失败'
}

export default ReportPage
