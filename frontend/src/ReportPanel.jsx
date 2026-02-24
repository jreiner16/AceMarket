// ReportPanel -- display of portfolio and backtesting metrics/reports
import { useEffect, useMemo, useState } from 'react'
import { ConfirmDialog } from './ConfirmDialog'
import { apiGet, apiDelete } from './apiClient'

function fmtMoney(n) {
  const x = Number(n)
  if (!Number.isFinite(x)) return '—'
  return x.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtPct(n) {
  const x = Number(n)
  if (!Number.isFinite(x)) return '—'
  return `${x.toFixed(2)}%`
}

function downloadText(filename, text, mime = 'text/plain') {
  const blob = new Blob([text], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function toCsv(rows, columns) {
  const esc = (v) => {
    if (v == null) return ''
    const s = String(v)
    if (/[,"\n]/.test(s)) return `"${s.replaceAll('"', '""')}"`
    return s
  }
  const header = columns.map((c) => esc(c.label)).join(',')
  const lines = rows.map((r) => columns.map((c) => esc(c.value(r))).join(','))
  return [header, ...lines].join('\n')
}

function LineChart({ points, color = '#000', fillColor, formatValue, height = 80 }) {
  const values = (points || []).map((p) => Number(p?.v)).filter((v) => Number.isFinite(v))
  if (values.length < 2) return <div className="report-legacy-muted">No series</div>

  const chartW = 600
  const h = height
  const pad = 6
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const pts = points.length === 1 ? [points[0], points[0]] : points

  const fmt = formatValue || ((v) => String(v))
  const ticks = [max, min]
  if (range > 0) {
    const mid = min + range / 2
    if (Math.abs(mid - min) > range * 0.15 && Math.abs(max - mid) > range * 0.15) {
      ticks.splice(1, 0, mid)
    }
  }

  const coords = pts.map((p, i) => {
    const v = Number(p?.v)
    const x = pad + (pts.length > 1 ? i / (pts.length - 1) : 0) * (chartW - pad * 2)
    const y = h - pad - ((v - min) / range) * (h - pad * 2)
    return { x, y }
  })
  const d = coords.map((c) => `${c.x},${c.y}`).join(' ')
  const areaPoints = fillColor
    ? `${pad},${h - pad} ${d} ${chartW - pad},${h - pad}`
    : null

  return (
    <div className="report-chart-with-scale" style={{ height }}>
      {formatValue && (
        <div className="report-chart-y-scale">
          {ticks.map((t, i) => (
            <span key={i}>{fmt(t)}</span>
          ))}
        </div>
      )}
      <svg viewBox={`0 0 ${chartW} ${h}`} preserveAspectRatio="none" className="report-legacy-chart">
        {areaPoints && (
          <polygon points={areaPoints} fill={fillColor} stroke="none" />
        )}
        <polyline points={d} fill="none" stroke={color} strokeWidth="2.5" vectorEffect="non-scaling-stroke" />
      </svg>
    </div>
  )
}

function DrawdownChart({ equityMetrics, height = 60 }) {
  const dd = equityMetrics?.drawdown_series
  if (!Array.isArray(dd) || dd.length < 2) return <div className="report-legacy-muted">No drawdown</div>
  const points = dd.map((v, i) => ({ i, v }))
  return (
    <LineChart
      points={points}
      color="#7a0000"
      fillColor="rgba(122,0,0,0.18)"
      formatValue={(v) => `${Number(v).toFixed(1)}%`}
      height={height}
    />
  )
}

function pickView(portfolio, run) {
  if (run?.portfolio) {
    return {
      kind: 'run',
      title: 'Backtest Run',
      value: run.portfolio.value,
      cash: null,
      initialCash: run.portfolio.initial_cash,
      tradeLog: run.portfolio.trade_log || [],
      equityCurve: run.portfolio.equity_curve || [],
      metrics: run.metrics || null,
      run,
    }
  }
  return {
    kind: 'live',
    title: 'Live Portfolio',
    value: portfolio?.value,
    cash: portfolio?.cash,
    initialCash: portfolio?.initial_cash,
    tradeLog: portfolio?.trade_log || [],
    equityCurve: portfolio?.equity_curve || [],
    metrics: portfolio?.metrics || null,
    run: null,
  }
}

export function ReportPanel({ refresh, onMatchFrame }) {
  const [portfolio, setPortfolio] = useState(null)
  const [runs, setRuns] = useState([])
  const [mode, setMode] = useState('live') // 'live' | 'run'
  const [runId, setRunId] = useState('')
  const [runDetail, setRunDetail] = useState(null)
  const [tab, setTab] = useState('overview') // overview | performance | trades | raw

  const [tradeSymbol, setTradeSymbol] = useState('ALL')
  const [tradeType, setTradeType] = useState('ALL')
  const [tradeStart, setTradeStart] = useState('')
  const [tradeEnd, setTradeEnd] = useState('')
  const [tradeSearch, setTradeSearch] = useState('')
  const [onlyExits, setOnlyExits] = useState(false)
  const [sortKey, setSortKey] = useState('index')
  const [sortDir, setSortDir] = useState('desc')

  useEffect(() => {
    apiGet('/portfolio')
      .then(setPortfolio)
      .catch(() => setPortfolio(null))

    apiGet('/runs')
      .then((d) => setRuns(d.runs || []))
      .catch(() => setRuns([]))
  }, [refresh])

  useEffect(() => {
    if (mode !== 'run') return
    if (!runId && runs.length) {
      setRunId(String(runs[0].id))
    }
  }, [mode, runId, runs])

  useEffect(() => {
    if (mode !== 'run') {
      setRunDetail(null)
      return
    }
    if (!runId) {
      setRunDetail(null)
      return
    }
    apiGet(`/runs/${runId}`)
      .then(setRunDetail)
      .catch(() => setRunDetail({ run: null, error: 'Failed to load run' }))
  }, [mode, runId])

  const view = useMemo(() => pickView(portfolio, runDetail?.run), [portfolio, runDetail])

  const allSymbols = useMemo(() => {
    const set = new Set()
    for (const t of view.tradeLog || []) set.add(String(t.stock || '').toUpperCase())
    return Array.from(set).filter(Boolean).sort()
  }, [view.tradeLog])

  const filteredTrades = useMemo(() => {
    const q = tradeSearch.trim().toLowerCase()
    const start = tradeStart || null
    const end = tradeEnd || null

    let rows = (view.tradeLog || []).slice()
    if (onlyExits) rows = rows.filter((t) => String(t.type || '').toLowerCase() === 'exit')
    if (tradeSymbol !== 'ALL') rows = rows.filter((t) => String(t.stock || '').toUpperCase() === tradeSymbol)
    if (tradeType !== 'ALL') rows = rows.filter((t) => String(t.type || '').toLowerCase() === tradeType.toLowerCase())
    if (start) rows = rows.filter((t) => (t.time ? String(t.time) >= start : true))
    if (end) rows = rows.filter((t) => (t.time ? String(t.time) <= end : true))
    if (q) {
      rows = rows.filter((t) => {
        const parts = [
          t.type,
          t.stock,
          t.time,
          t.quantity,
          t.price,
          t.fill_price,
          t.realized_pnl,
        ].map((x) => (x == null ? '' : String(x).toLowerCase()))
        return parts.some((p) => p.includes(q))
      })
    }

    const key = sortKey
    const dir = sortDir === 'asc' ? 1 : -1
    const get = (t) => {
      if (key === 'time') return String(t.time || '')
      if (key === 'stock') return String(t.stock || '')
      if (key === 'type') return String(t.type || '')
      return Number(t[key]) || 0
    }
    rows.sort((a, b) => {
      const av = get(a)
      const bv = get(b)
      if (typeof av === 'string' || typeof bv === 'string') return String(av).localeCompare(String(bv)) * dir
      return (av - bv) * dir
    })
    return rows
  }, [view.tradeLog, tradeSearch, tradeStart, tradeEnd, tradeSymbol, tradeType, onlyExits, sortKey, sortDir])

  const equity = view.metrics?.equity
  const trades = view.metrics?.trades
  const symbols = view.metrics?.symbols || []

  const setSort = (k) => {
    if (sortKey === k) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else {
      setSortKey(k)
      setSortDir('desc')
    }
  }

  const exportTradesCsv = () => {
    const cols = [
      { label: 'time', value: (t) => t.time || '' },
      { label: 'index', value: (t) => t.index ?? '' },
      { label: 'type', value: (t) => t.type || '' },
      { label: 'symbol', value: (t) => t.stock || '' },
      { label: 'qty', value: (t) => t.quantity ?? '' },
      { label: 'price', value: (t) => t.price ?? '' },
      { label: 'fill_price', value: (t) => t.fill_price ?? '' },
      { label: 'cost', value: (t) => t.cost ?? '' },
      { label: 'proceeds', value: (t) => t.proceeds ?? '' },
      { label: 'amount', value: (t) => t.amount ?? '' },
      { label: 'realized_pnl', value: (t) => t.realized_pnl ?? '' },
    ]
    const csv = toCsv(filteredTrades, cols)
    const name = view.kind === 'run' ? `run-${runId}-trades.csv` : 'portfolio-trades.csv'
    downloadText(name, csv, 'text/csv')
  }

  const [confirmClear, setConfirmClear] = useState(false)

  const clearRunHistory = async () => {
    setConfirmClear(true)
  }

  const doClearRunHistory = async () => {
    setConfirmClear(false)
    try {
      await apiDelete('/runs')
      setRuns([])
      setRunId('')
      setRunDetail(null)
    } catch {
      // ignore
    }
  }

  const headlinePnl = (equity?.pnl ?? (Number(view.value) - Number(view.initialCash)))
  const headlinePnlOk = Number.isFinite(Number(headlinePnl))

  return (
    <div className="report-panel report-legacy">
      <div className="report-header report-legacy-header">
        <span className="report-title">Strategy Tester</span>
        <div className="report-legacy-tabs">
          <button type="button" className={tab === 'overview' ? 'active' : ''} onClick={() => setTab('overview')}>Overview</button>
          <button type="button" className={tab === 'performance' ? 'active' : ''} onClick={() => setTab('performance')}>Performance</button>
          <button type="button" className={tab === 'trades' ? 'active' : ''} onClick={() => setTab('trades')}>Trades</button>
          <button type="button" className={tab === 'raw' ? 'active' : ''} onClick={() => setTab('raw')}>Raw</button>
        </div>
      </div>

      <div className="report-toolbar">
        <div className="report-legacy-mode">
          <label>
            <input type="radio" checked={mode === 'live'} onChange={() => setMode('live')} />
            Live
          </label>
          <label>
            <input type="radio" checked={mode === 'run'} onChange={() => setMode('run')} />
            Runs
          </label>
          {mode === 'run' && (
            <select value={runId} onChange={(e) => setRunId(e.target.value)} disabled={!runs.length}>
              {!runs.length && <option value="">No saved runs</option>}
              {runs.map((r) => (
                <option key={r.id} value={String(r.id)}>
                  #{r.id} {r.strategy} ({(r.symbols || []).join(', ') || '—'})
                </option>
              ))}
            </select>
          )}
          {mode === 'run' && (
            <button type="button" onClick={clearRunHistory} disabled={!runs.length}>
              Clear
            </button>
          )}
          {view.kind === 'run' && view.run?.start_date && view.run?.end_date && onMatchFrame && (
            <button type="button" className="report-match-frame-btn" onClick={() => onMatchFrame({ startDate: view.run.start_date, endDate: view.run.end_date })}>
              Match frame
            </button>
          )}
        </div>
        <div className="report-legacy-headline">
          <span><strong>{view.title}:</strong> ${fmtMoney(view.value)}</span>
          {headlinePnlOk && (
            <span className={Number(headlinePnl) >= 0 ? 'pos' : 'neg'}>
              ({Number(headlinePnl) >= 0 ? '+' : ''}${fmtMoney(headlinePnl)})
            </span>
          )}
        </div>
      </div>

      <div className="report-content report-legacy-content">
        {tab === 'overview' && (
          <div className="report-legacy-section">
            {view.kind === 'run' && view.run && (
              <fieldset>
                <legend>Run Info</legend>
                <table className="report-legacy-kv">
                  <tbody>
                    <tr><th>Run</th><td>#{view.run.id}</td><th>Strategy</th><td>{view.run.strategy}</td></tr>
                    <tr><th>Symbols</th><td colSpan={3}>{(view.run.symbols || []).join(', ') || '—'}</td></tr>
                    <tr><th>Window</th><td colSpan={3}>{view.run.start_date} to {view.run.end_date}</td></tr>
                    <tr><th>Slippage</th><td>{view.run.settings?.slippage ?? '—'}</td><th>Commission</th><td>{view.run.settings?.commission ?? '—'}</td></tr>
                    <tr><th>Allow Short</th><td>{String(Boolean(view.run.settings?.allow_short))}</td><th>Auto-liquidate</th><td>{String(Boolean(view.run.settings?.auto_liquidate_end ?? true))}</td></tr>
                    <tr><th>Max Positions</th><td>{view.run.settings?.max_positions ?? 0}</td><th>Max Pos %</th><td>{view.run.settings?.max_position_pct ?? 0}</td></tr>
                    <tr><th>Cash Reserve %</th><td>{view.run.settings?.min_cash_reserve_pct ?? 0}</td><th>Min Trade $</th><td>{view.run.settings?.min_trade_value ?? 0}</td></tr>
                    <tr><th>Max Trade $</th><td>{view.run.settings?.max_trade_value ?? 0}</td><th>Max Qty</th><td>{view.run.settings?.max_order_qty ?? 0}</td></tr>
                  </tbody>
                </table>
              </fieldset>
            )}

            <fieldset>
              <legend>Headline</legend>
              {!equity ? (
                <div className="report-legacy-muted">No metrics yet.</div>
              ) : (
                <table className="report-legacy-kv">
                  <tbody>
                    <tr>
                      <th>Start</th><td>${fmtMoney(equity.start_value)}</td>
                      <th>End</th><td>${fmtMoney(equity.end_value)}</td>
                    </tr>
                    <tr>
                      <th>Total Return</th><td>{fmtPct(equity.total_return_pct)}</td>
                      <th>Max Drawdown</th><td>{fmtPct(equity.max_drawdown_pct)}</td>
                    </tr>
                    <tr>
                      <th>Trades</th><td>{trades?.trades ?? 0}</td>
                      <th>Win Rate</th><td>{fmtPct(trades?.win_rate_pct)}</td>
                    </tr>
                    <tr>
                      <th>Profit Factor</th><td>{trades?.profit_factor == null ? '—' : Number(trades.profit_factor).toFixed(2)}</td>
                      <th>Net Realized</th><td>${fmtMoney(trades?.net_realized_exits)}</td>
                    </tr>
                  </tbody>
                </table>
              )}
            </fieldset>

            <fieldset>
              <legend>Equity (quick)</legend>
              <LineChart
                points={view.equityCurve}
                color="#0b5d1e"
                fillColor="rgba(11,93,30,0.18)"
                formatValue={(v) => `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                height={80}
              />
            </fieldset>

            <fieldset>
              <legend>By Symbol (realized on exits)</legend>
              {symbols.length === 0 ? (
                <div className="report-legacy-muted">No symbols yet.</div>
              ) : (
                <table className="report-legacy-table">
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Trades</th>
                      <th>Exits</th>
                      <th>Net Realized</th>
                    </tr>
                  </thead>
                  <tbody>
                    {symbols.map((s) => (
                      <tr key={s.symbol}>
                        <td>{s.symbol}</td>
                        <td>{s.trades}</td>
                        <td>{s.exits}</td>
                        <td className={Number(s.net_realized) >= 0 ? 'pos' : 'neg'}>${fmtMoney(s.net_realized)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </fieldset>

            {mode === 'run' && (
              <fieldset>
                <legend>Saved Runs</legend>
                {runs.length === 0 ? (
                  <div className="report-legacy-muted">No saved runs yet. Run a strategy to generate one.</div>
                ) : (
                  <table className="report-legacy-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Strategy</th>
                        <th>Symbols</th>
                        <th>Window</th>
                        <th>PnL</th>
                        <th>Max DD</th>
                        <th>Win%</th>
                      </tr>
                    </thead>
                    <tbody>
                      {runs.map((r) => (
                        <tr key={r.id} className={String(r.id) === String(runId) ? 'active' : ''}>
                          <td>
                            <button type="button" className="report-legacy-link" onClick={() => { setMode('run'); setRunId(String(r.id)); }}>
                              #{r.id}
                            </button>
                          </td>
                          <td>{r.strategy}</td>
                          <td>{(r.symbols || []).join(', ')}</td>
                          <td>{r.start_date} → {r.end_date}</td>
                          <td className={Number(r.pnl) >= 0 ? 'pos' : 'neg'}>${fmtMoney(r.pnl)}</td>
                          <td className="neg">{fmtPct(r.max_drawdown_pct)}</td>
                          <td>{fmtPct(r.win_rate_pct)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </fieldset>
            )}
          </div>
        )}

        {tab === 'performance' && (
          <div className="report-legacy-section">
            <div className="report-charts-with-frame">
              <fieldset>
                <legend>Equity Curve</legend>
                <LineChart
                  points={view.equityCurve}
                  color="#0b5d1e"
                  fillColor="rgba(11,93,30,0.18)"
                  formatValue={(v) => `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                  height={120}
                />
              </fieldset>
              <fieldset>
                <legend>Drawdown</legend>
                <DrawdownChart equityMetrics={equity} height={80} />
              </fieldset>
            </div>
            <fieldset>
              <legend>Return Stats (trade-to-trade)</legend>
              {!equity ? (
                <div className="report-legacy-muted">No stats yet.</div>
              ) : (
                <table className="report-legacy-kv">
                  <tbody>
                    <tr><th>Avg Return</th><td>{fmtPct(equity.trade_to_trade_avg_return_pct)}</td><th>Stdev</th><td>{fmtPct(equity.trade_to_trade_stdev_return * 100)}</td></tr>
                    <tr><th>Sharpe-like</th><td>{Number(equity.trade_to_trade_sharpe_like || 0).toFixed(3)}</td><th>Points</th><td>{equity.points}</td></tr>
                  </tbody>
                </table>
              )}
              <div className="report-legacy-muted">
                Note: these stats are computed from equity changes after trades (not time-normalized).
              </div>
            </fieldset>
          </div>
        )}

        {tab === 'trades' && (
          <div className="report-legacy-section">
            <fieldset>
              <legend>Filters</legend>
              <div className="report-legacy-filters">
                <label>
                  Symbol
                  <select value={tradeSymbol} onChange={(e) => setTradeSymbol(e.target.value)}>
                    <option value="ALL">ALL</option>
                    {allSymbols.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </label>
                <label>
                  Type
                  <select value={tradeType} onChange={(e) => setTradeType(e.target.value)}>
                    <option value="ALL">ALL</option>
                    <option value="long">long</option>
                    <option value="short">short</option>
                    <option value="exit">exit</option>
                  </select>
                </label>
                <label>
                  Start
                  <input type="date" value={tradeStart} onChange={(e) => setTradeStart(e.target.value)} />
                </label>
                <label>
                  End
                  <input type="date" value={tradeEnd} onChange={(e) => setTradeEnd(e.target.value)} />
                </label>
                <label>
                  Search
                  <input value={tradeSearch} onChange={(e) => setTradeSearch(e.target.value)} placeholder="symbol, price, pnl, …" />
                </label>
                <label className="report-legacy-checkbox">
                  <input type="checkbox" checked={onlyExits} onChange={(e) => setOnlyExits(e.target.checked)} />
                  only exits
                </label>
                <button type="button" onClick={exportTradesCsv} disabled={!filteredTrades.length}>
                  Export CSV
                </button>
              </div>
            </fieldset>

            <fieldset>
              <legend>Trades ({filteredTrades.length})</legend>
              {filteredTrades.length === 0 ? (
                <div className="report-legacy-muted">No trades match filters.</div>
              ) : (
                <table className="report-legacy-table report-legacy-table-trades">
                  <thead>
                    <tr>
                      <th><button type="button" onClick={() => setSort('time')}>Time</button></th>
                      <th><button type="button" onClick={() => setSort('type')}>Type</button></th>
                      <th><button type="button" onClick={() => setSort('stock')}>Symbol</button></th>
                      <th><button type="button" onClick={() => setSort('quantity')}>Qty</button></th>
                      <th><button type="button" onClick={() => setSort('price')}>Price</button></th>
                      <th><button type="button" onClick={() => setSort('fill_price')}>Fill</button></th>
                      <th><button type="button" onClick={() => setSort('realized_pnl')}>Realized</button></th>
                      <th><button type="button" onClick={() => setSort('index')}>Idx</button></th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredTrades.map((t, i) => (
                      <tr key={i} className={`t-${String(t.type || '').toLowerCase()}`}>
                        <td>{t.time || '—'}</td>
                        <td>{t.type}</td>
                        <td>{t.stock}</td>
                        <td>{t.quantity}</td>
                        <td>${fmtMoney(t.price)}</td>
                        <td>${fmtMoney(t.fill_price)}</td>
                        <td className={Number(t.realized_pnl) >= 0 ? 'pos' : 'neg'}>${fmtMoney(t.realized_pnl)}</td>
                        <td>{t.index ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <div className="report-legacy-muted">
                Sort: {sortKey} ({sortDir}). Entries can realize PnL when flipping direction.
              </div>
            </fieldset>
          </div>
        )}

        {tab === 'raw' && (
          <div className="report-legacy-section">
            <fieldset>
              <legend>Raw JSON</legend>
              <div className="report-legacy-raw-actions">
                <button
                  type="button"
                  onClick={() => downloadText(view.kind === 'run' ? `run-${runId}.json` : 'portfolio.json', JSON.stringify(view.kind === 'run' ? view.run : portfolio, null, 2), 'application/json')}
                >
                  Download JSON
                </button>
              </div>
              <pre className="report-legacy-pre">
                {JSON.stringify(view.kind === 'run' ? view.run : portfolio, null, 2)}
              </pre>
            </fieldset>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={confirmClear}
        title="Clear runs"
        message="Clear all saved backtest runs?"
        confirmLabel="Clear"
        onConfirm={doClearRunHistory}
        onCancel={() => setConfirmClear(false)}
      />
    </div>
  )
}
