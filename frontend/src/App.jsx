import { useState, useCallback, useEffect } from 'react'
import { subscribe } from './consoleStore'
import { useAuth } from './authContext'
import { useUserData } from './useUserData'
import { SplashPage } from './SplashPage'
import { StockChart } from './StockChart'
import { OrderPanel } from './OrderPanel'
import { PortfolioPanel } from './PortfolioPanel'
import { ReportPanel } from './ReportPanel'
import { ConsolePanel } from './ConsolePanel'
import { StrategyPanel } from './StrategyPanel'
import { Watchlist } from './Watchlist'
import { ResizeHandle } from './ResizeHandle'
import { SettingsModal } from './SettingsModal'
import { ConfirmDialog } from './ConfirmDialog'
import './App.css'

const MIN_LEFT = 180
const MAX_LEFT = 450
const MIN_RIGHT = 200
const MAX_RIGHT = 500
const MIN_REPORT = 80
const MAX_REPORT = 400

function App() {
  const { user, loading: authLoading, signOut } = useAuth()
  const { watchlist, setWatchlist } = useUserData(user)

  const [selectedSymbol, setSelectedSymbol] = useState(null)
  const [price, setPrice] = useState(null)
  const [portfolioRefresh, setPortfolioRefresh] = useState(0)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [leftWidth, setLeftWidth] = useState(280)
  const [rightWidth, setRightWidth] = useState(320)
  const [reportHeight, setReportHeight] = useState(180)
  const [reportTab, setReportTab] = useState('report') // 'report' | 'console'
  const [rightTab, setRightTab] = useState('orders') // 'orders' | 'strategies'
  const [reportMaximized, setReportMaximized] = useState(false)
  const [strategyMaximized, setStrategyMaximized] = useState(false)
  const [consoleErrorCount, setConsoleErrorCount] = useState(0)
  const [chartDateRange, setChartDateRange] = useState(null) // { startDate, endDate } | null
  const [chartShowSma, setChartShowSma] = useState(false)
  const [chartShowEma, setChartShowEma] = useState(false)
  const [chartShowRsi, setChartShowRsi] = useState(false)
  const [confirmSignOut, setConfirmSignOut] = useState(false)

  useEffect(() => {
    return subscribe((entries) => {
      setConsoleErrorCount(entries.filter((e) => e.level === 'error').length)
    })
  }, [])

  const handleSelectStock = useCallback((symbol) => {
    setSelectedSymbol(symbol)
    if (!watchlist.includes(symbol)) {
      setWatchlist((w) => [...w, symbol].slice(-30))
    }
  }, [watchlist])

  const handleAddToWatchlist = useCallback((symbol) => {
    if (symbol && !watchlist.includes(symbol)) {
      setWatchlist((w) => [...w, symbol].slice(-30))
    }
  }, [watchlist])

  const handleRemoveFromWatchlist = useCallback((symbol) => {
    const newList = watchlist.filter((s) => s !== symbol)
    setWatchlist(newList)
    if (selectedSymbol === symbol) {
      setSelectedSymbol(newList[0] || null)
    }
  }, [watchlist, selectedSymbol])

  const handleOrder = useCallback(() => {
    setPortfolioRefresh((r) => r + 1)
  }, [])

  const handleResizeLeft = useCallback((dx) => {
    setLeftWidth((w) => Math.min(MAX_LEFT, Math.max(MIN_LEFT, w + dx)))
  }, [])

  const handleResizeRight = useCallback((dx) => {
    setRightWidth((w) => Math.min(MAX_RIGHT, Math.max(MIN_RIGHT, w - dx)))
  }, [])

  const handleResizeReport = useCallback((_, dy) => {
    setReportHeight((h) => Math.min(MAX_REPORT, Math.max(MIN_REPORT, h - dy)))
  }, [])

  if (authLoading) {
    return (
      <div className="app app-loading">
        <div className="app-loading-spinner" />
        <span>Loading…</span>
      </div>
    )
  }

  if (!user) {
    return <SplashPage />
  }

  return (
    <div className="app">
      <header className="header">
        <div className="logo">
          <img className="logo-mark" src="/logo.svg" alt="AceMarket" />
          <span>AceMarket</span>
        </div>
        <div className="header-actions">
          <span className="header-account">Your account</span>
          <span className="header-user">{user.email}</span>
          <button type="button" className="header-settings-btn" onClick={() => setSettingsOpen(true)} title="Settings" aria-label="Settings">
            {"\u2699"}
          </button>
          <button type="button" className="header-signout" onClick={() => setConfirmSignOut(true)} title="Sign out">
            Sign out
          </button>
        </div>
      </header>

      <div className="app-body">
        <div className="app-body-left">
          <div className="app-body-top">
            <aside className="sidebar-left" style={{ width: leftWidth }}>
              <Watchlist
                items={watchlist}
                selectedSymbol={selectedSymbol}
                onSelect={handleSelectStock}
                onAdd={handleAddToWatchlist}
                onRemove={handleRemoveFromWatchlist}
              />
            </aside>
            <ResizeHandle direction="vertical" onResize={handleResizeLeft} />
            <main className="chart-area">
              <div className="chart-header">
                {selectedSymbol && (
                  <>
                    <span className="chart-symbol">{selectedSymbol}</span>
                    {price != null && (
                      <span className="chart-price">${price.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                    )}
                    {chartDateRange && (
                      <span className="chart-date-range">
                        {chartDateRange.startDate} – {chartDateRange.endDate}
                        <button type="button" className="chart-clear-frame" onClick={() => setChartDateRange(null)} title="Clear date range">×</button>
                      </span>
                    )}
                    <div className="chart-indicators">
                      <label className="chart-indicator-check">
                        <input type="checkbox" checked={chartShowSma} onChange={(e) => setChartShowSma(e.target.checked)} />
                        <span>SMA</span>
                      </label>
                      <label className="chart-indicator-check">
                        <input type="checkbox" checked={chartShowEma} onChange={(e) => setChartShowEma(e.target.checked)} />
                        <span>EMA</span>
                      </label>
                      <label className="chart-indicator-check">
                        <input type="checkbox" checked={chartShowRsi} onChange={(e) => setChartShowRsi(e.target.checked)} />
                        <span>RSI</span>
                      </label>
                    </div>
                  </>
                )}
              </div>
              <div className="chart-container">
                {selectedSymbol ? (
                  <StockChart
                    key={`${selectedSymbol}-${chartDateRange?.startDate ?? ''}-${chartDateRange?.endDate ?? ''}-${chartShowSma}-${chartShowEma}-${chartShowRsi}`}
                    symbol={selectedSymbol}
                    startDate={chartDateRange?.startDate}
                    endDate={chartDateRange?.endDate}
                    onPriceUpdate={setPrice}
                    showSma={chartShowSma}
                    showEma={chartShowEma}
                    showRsi={chartShowRsi}
                  />
                ) : (
                  <div className="empty-chart">Search and select a stock to view the chart</div>
                )}
              </div>
            </main>
          </div>

          {!reportMaximized && (
            <ResizeHandle direction="horizontal" onResize={handleResizeReport} />
          )}

          <div
            className={`report-window ${reportMaximized ? 'maximized' : ''}`}
            style={reportMaximized ? undefined : { height: reportHeight }}
          >
            <div className="report-tabs">
              <button
                type="button"
                className={`report-tab ${reportTab === 'report' ? 'active' : ''}`}
                onClick={() => setReportTab('report')}
              >
                Report
              </button>
              <button
                type="button"
                className={`report-tab ${reportTab === 'console' ? 'active' : ''}`}
                onClick={() => setReportTab('console')}
              >
                Console
                {consoleErrorCount > 0 && (
                  <span className="report-tab-badge">{consoleErrorCount}</span>
                )}
              </button>
              <button
                type="button"
                className="report-tab report-tab-maximize"
                onClick={() => setReportMaximized((m) => !m)}
                title={reportMaximized ? 'Restore' : 'Maximize'}
              >
                {reportMaximized ? '⊟' : '⊞'}
              </button>
            </div>
            {reportTab === 'report' ? (
              <ReportPanel
                refresh={portfolioRefresh}
                onMatchFrame={setChartDateRange}
              />
            ) : (
              <ConsolePanel />
            )}
          </div>
        </div>

        <ResizeHandle direction="vertical" onResize={handleResizeRight} />

        <aside className="sidebar-right" style={{ width: rightWidth }}>
          <div className="sidebar-right-tabs">
            <button
              type="button"
              className={`sidebar-right-tab ${rightTab === 'orders' ? 'active' : ''}`}
              onClick={() => setRightTab('orders')}
            >
              Orders
            </button>
            <button
              type="button"
              className={`sidebar-right-tab ${rightTab === 'strategies' ? 'active' : ''}`}
              onClick={() => setRightTab('strategies')}
            >
              Strategies
            </button>
            {rightTab === 'strategies' && (
              <button
                type="button"
                className="sidebar-right-tab sidebar-right-tab-maximize"
                onClick={() => setStrategyMaximized((m) => !m)}
                title={strategyMaximized ? 'Restore' : 'Maximize'}
              >
                {strategyMaximized ? '⊟' : '⊞'}
              </button>
            )}
          </div>
          {rightTab === 'orders' ? (
            <>
              <OrderPanel
                symbol={selectedSymbol}
                price={price}
                onOrder={handleOrder}
              />
              <PortfolioPanel refresh={portfolioRefresh} />
            </>
          ) : !strategyMaximized ? (
            <div className="sidebar-right-strategies">
              <StrategyPanel
                watchlist={watchlist}
                refresh={portfolioRefresh}
                onRefresh={() => setPortfolioRefresh((r) => r + 1)}
                compact
              />
            </div>
          ) : null}
        </aside>
      </div>

      {strategyMaximized && rightTab === 'strategies' && (
        <div className="strategy-maximized-overlay">
          <div className="strategy-maximized-header">
            <span>Strategies</span>
            <button
              type="button"
              className="strategy-maximize-btn"
              onClick={() => setStrategyMaximized(false)}
              title="Restore"
            >
              ⊟
            </button>
          </div>
          <div className="strategy-maximized-body">
            <StrategyPanel
              watchlist={watchlist}
              refresh={portfolioRefresh}
              onRefresh={() => setPortfolioRefresh((r) => r + 1)}
              compact
            />
          </div>
        </div>
      )}

      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onClearHistory={() => setPortfolioRefresh((r) => r + 1)}
        user={user}
      />
      <ConfirmDialog
        open={confirmSignOut}
        title="Sign out"
        message="Are you sure you want to sign out?"
        confirmLabel="Sign out"
        onConfirm={() => {
          setConfirmSignOut(false)
          signOut()
        }}
        onCancel={() => setConfirmSignOut(false)}
      />
    </div>
  )
}

export default App
