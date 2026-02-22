import { useState, useEffect } from 'react'
import { apiGet, apiPost } from './apiClient'

export function PortfolioPanel({ refresh }) {
  const [portfolio, setPortfolio] = useState(null)

  const load = () => {
    apiGet('/portfolio')
      .then(setPortfolio)
      .catch(() => setPortfolio(null))
  }

  useEffect(load, [refresh])

  const handleClose = async (symbol, quantity) => {
    try {
      await apiPost('/portfolio/position/close', { symbol, quantity })
      load()
    } catch (err) {
      console.error('Portfolio:', err.detail || err.message || 'Failed to close position')
    }
  }

  if (!portfolio) return <div className="portfolio-panel">Loading...</div>

  return (
    <div className="portfolio-panel">
      <div className="portfolio-summary">
        <div className="portfolio-stat">
          <div className="portfolio-stat-label">Buying Power</div>
          <div className="portfolio-stat-value">
            ${portfolio.buying_power?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
        </div>
        <div className="portfolio-stat">
          <div className="portfolio-stat-label">Total Value</div>
          <div className="portfolio-stat-value">
            ${portfolio.value?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
        </div>
        <div className="portfolio-stat cash">
          <div className="portfolio-stat-label">Cash</div>
          <div className="portfolio-stat-value">
            ${portfolio.cash?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
        </div>
      </div>
      {(portfolio.short_exposure != null || portfolio.reserved_cash != null) && (
        <div className="portfolio-substats">
          <span>Short Exposure: ${portfolio.short_exposure?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
          <span>Reserved: ${portfolio.reserved_cash?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
        </div>
      )}
      <div className="positions-title">Positions</div>
      {!portfolio.positions?.length ? (
        <div className="empty-portfolio">No open positions</div>
      ) : (
        portfolio.positions.map((p) => (
          <div key={p.symbol} className="position-row">
            <div>
              <div className="position-symbol">{p.symbol}</div>
              <div className="position-qty">
                {p.quantity} {p.side}
              </div>
            </div>
            <div className={`position-pnl ${p.pnl >= 0 ? 'positive' : 'negative'}`}>
              ${p.pnl?.toFixed(2)} ({p.pnl_pct?.toFixed(1)}%)
            </div>
            <button
              className="position-close-btn"
              onClick={() => handleClose(p.symbol, p.quantity)}
            >
              Close
            </button>
          </div>
        ))
      )}
    </div>
  )
}
