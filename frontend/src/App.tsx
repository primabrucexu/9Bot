import { NavLink, Route, Routes } from 'react-router-dom'
import DashboardPage from './pages/DashboardPage'
import ReportPage from './pages/ReportPage'
import StockDetailPage from './pages/StockDetailPage'

function App() {
  return (
    <>
      <header className="site-header">
        <div className="site-shell">
          <div>
            <p className="eyebrow">Personal A-share Lab</p>
            <NavLink className="brand" to="/">
              9Bot
            </NavLink>
          </div>
          <nav className="site-nav">
            <NavLink className={getNavClassName} to="/" end>
              看板
            </NavLink>
            <NavLink className={getNavClassName} to="/reports/latest">
              日报
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="site-shell page-shell">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/stocks/:symbol" element={<StockDetailPage />} />
          <Route path="/reports/latest" element={<ReportPage mode="latest" />} />
          <Route path="/reports/:reportDate" element={<ReportPage mode="byDate" />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
    </>
  )
}

function getNavClassName({ isActive }: { isActive: boolean }) {
  return isActive ? 'active' : undefined
}

function NotFoundPage() {
  return (
    <section className="panel empty-state">
      <h2>页面不存在</h2>
      <p>请从导航返回看板或日报页面。</p>
    </section>
  )
}

export default App
