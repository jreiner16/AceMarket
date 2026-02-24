// StrategyPanel -- create/run strategies with custom python framework
import { useState, useEffect, useCallback, useRef } from 'react'
import Editor from 'react-simple-code-editor'
import { highlight, languages } from 'prismjs'
import 'prismjs/components/prism-python'
import { ResizeHandle } from './ResizeHandle'
import { ConfirmDialog } from './ConfirmDialog'
import { apiGet, apiPost, apiPut, apiDelete } from './apiClient'

const DEFAULT_CODE = `# Example strategy: EMA/SMA Crossover Strategy (slippage/commission-aware sizing)
class MyStrategy(Strategy):
    def __init__(self, stock, portfolio):
        super().__init__(stock, portfolio)
        self.short_period = 10
        self.long_period = 30

    def start(self, candle=None):
        """Called once at the beginning of the backtest."""
        pass

    def update(self, open, high, low, close, index=None):
        """Called for each candle during the backtest."""
        if index is None or index < self.long_period:
            return

        sma_short = self.stock.sma(self.short_period)
        sma_long = self.stock.sma(self.long_period)
        short = sma_short[index]
        long_val = sma_long[index]
        prev_short = sma_short[index - 1]
        prev_long = sma_long[index - 1]

        in_position = any(s[0] == self.stock for s in self.portfolio.stocks)
        qty = next((q for s, q in self.portfolio.stocks if s == self.stock), 0)

        # Golden cross: short crosses above long -> buy
        if not in_position and prev_short <= prev_long and short > long_val:
            # Size using estimated fill (accounts for slippage + commission).
            buy_fill = self.portfolio.estimate_fill_price('buy', close)
            if buy_fill <= 0:
                return
            shares = int(self.portfolio.cash * 0.95 / buy_fill)
            if shares > 0:
                self.portfolio.enter_position_long(self.stock, shares, index)

        # Death cross: short crosses below long -> sell
        elif in_position and qty > 0 and prev_short >= prev_long and short < long_val:
            self.portfolio.exit_position(self.stock, qty, index)

    def end(self, candle=None):
        """Called once at the end of the backtest."""
        pass
`

export function StrategyPanel({ watchlist, refresh, onRefresh, compact }) {
  const [strategies, setStrategies] = useState([])
  const [selected, setSelected] = useState(null)
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [runModalOpen, setRunModalOpen] = useState(false)
  const [runSymbols, setRunSymbols] = useState([])
  const [stocksDropdownOpen, setStocksDropdownOpen] = useState(false)
  const [runStart, setRunStart] = useState('2023-01-01')
  const [runEnd, setRunEnd] = useState('2024-01-01')
  const [runTrainPct, setRunTrainPct] = useState('')  // e.g. 0.7 for 70% train, 30% OOS test
  const [runResults, setRunResults] = useState(null)
  const [running, setRunning] = useState(false)
  const [executingSymbols, setExecutingSymbols] = useState(new Set())
  const [filesWidth, setFilesWidth] = useState(120)
  const [apiKeyOpen, setApiKeyOpen] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(null)
  const stocksDropdownRef = useRef(null)

  useEffect(() => {
    if (!stocksDropdownOpen) return
    const onClickOutside = (e) => {
      if (stocksDropdownRef.current && !stocksDropdownRef.current.contains(e.target)) {
        setStocksDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [stocksDropdownOpen])

  const handleResizeFiles = useCallback((dx) => {
    setFilesWidth((w) => Math.min(240, Math.max(80, w + dx)))
  }, [])

  const load = () => {
    apiGet('/strategies')
      .then((d) => setStrategies(d.strategies || []))
      .catch(() => setStrategies([]))
  }

  useEffect(load, [refresh])

  const selectStrategy = (s) => {
    setSelected(s?.id ?? null)
    setName(s?.name ?? '')
    setCode(s?.code ?? '')
    setIsCreating(false)
  }

  const handleNew = () => {
    setSelected(null)
    setName('')
    setCode(DEFAULT_CODE)
    setIsCreating(true)
    setRunResults(null)
  }

  const handleSave = async () => {
    if (!name.trim()) {
      console.error('Strategy: Enter a name')
      return
    }
    if (!code.trim()) {
      console.error('Strategy: Code cannot be empty')
      return
    }
    try {
      if (selected) {
        await apiPut(`/strategies/${selected}`, { name: name.trim(), code })
      } else {
        const data = await apiPost('/strategies', { name: name.trim(), code })
        setSelected(data.strategy.id)
        setIsCreating(false)
      }
      load()
      onRefresh?.()
    } catch (e) {
      console.error('Strategy:', e.detail || e.message || 'Failed to save')
    }
  }

  const handleDelete = (id, stratName, e) => {
    e?.stopPropagation()
    setConfirmDelete({ id, name: stratName })
  }

  const doDelete = async () => {
    if (!confirmDelete) return
    const { id } = confirmDelete
    setConfirmDelete(null)
    try {
      await apiDelete(`/strategies/${id}`)
      if (selected === id) handleNew()
      load()
      onRefresh?.()
    } catch (e) {
      console.error('Strategy:', e.detail || e.message || 'Failed to delete')
    }
  }

  const openRunModal = () => {
    if (!selected) {
      console.error('Strategy: Select or create a strategy first')
      return
    }
    setRunModalOpen(true)
    setRunSymbols([])
    setRunResults(null)
    setStocksDropdownOpen(false)
  }

  const toggleRunSymbol = (sym) => {
    if (executingSymbols.has(sym)) return
    setRunSymbols((prev) =>
      prev.includes(sym) ? prev.filter((s) => s !== sym) : [...prev, sym]
    )
  }

  const handleExecute = async () => {
    if (runSymbols.length === 0) {
      console.error('Strategy: Select at least one stock')
      return
    }
    setRunning(true)
    setRunResults(null)
    setExecutingSymbols(new Set(runSymbols))
    try {
      const body = {
        strategy_id: selected,
        symbols: runSymbols,
        start_date: runStart,
        end_date: runEnd,
      }
      const trainPct = parseFloat(runTrainPct)
      if (Number.isFinite(trainPct) && trainPct > 0 && trainPct < 1) {
        body.train_pct = trainPct
      }
      const data = await apiPost('/strategies/run', body)
      setRunResults(data.results || [])
      onRefresh?.()
    } catch (e) {
      setRunResults([{ error: e.detail || e.message }])
    } finally {
      setRunning(false)
      setExecutingSymbols(new Set())
    }
  }

  const stocks = watchlist || []

  return (
    <div className={`strategy-panel ${compact ? 'compact' : ''}`}>
      <div className="strategy-content strategy-content-code">
        <div className="strategy-sidebar" style={{ width: filesWidth }}>
          <div className="strategy-files-header">
            <span className="strategy-files-title">Files</span>
            <button type="button" className="strategy-file-add" onClick={handleNew} title="New file">+</button>
          </div>
          {strategies.length === 0 && !isCreating ? (
            <div className="strategy-empty">No strategies</div>
          ) : (
            strategies.map((s) => (
              <div
                key={s.id}
                className={`strategy-file ${selected === s.id ? 'active' : ''}`}
                onClick={() => selectStrategy(s)}
              >
                <span className="strategy-file-name">{s.name}</span>
                <button
                  type="button"
                  className="strategy-file-delete"
                  onClick={(e) => handleDelete(s.id, s.name, e)}
                  title="Delete"
                >
                  ×
                </button>
              </div>
            ))
          )}
        </div>
        <ResizeHandle direction="vertical" onResize={handleResizeFiles} />
        <div className="strategy-main">
          {strategies.length === 0 && !isCreating ? (
            <div className="strategy-welcome">
              Click the <strong>+</strong> to create a new strategy file.
            </div>
          ) : (
            <>
              <div className="strategy-editor-header">
                <input
                  type="text"
                  className="strategy-name-input"
                  placeholder="Strategy name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
                <div className="strategy-editor-actions">
                  <button type="button" className="strategy-btn primary" onClick={handleSave}>
                    Save
                  </button>
                  <button type="button" className="strategy-btn primary" onClick={openRunModal} disabled={!selected}>
                    Run
                  </button>
                </div>
              </div>

              <div className="strategy-editor-wrap">
                <Editor
                  value={code}
                  onValueChange={setCode}
                  highlight={(c) => highlight(c, languages.python, 'python')}
                  padding={12}
                  className="strategy-editor"
                  textareaClassName="strategy-editor-textarea"
                  preClassName="strategy-editor-pre"
                />
              </div>
              <div className="strategy-api-key">
                <button
                  type="button"
                  className="strategy-api-key-toggle"
                  onClick={() => setApiKeyOpen((o) => !o)}
                >
                  {apiKeyOpen ? '▼' : '▶'} API Reference
                </button>
                {apiKeyOpen && (
                  <div className="strategy-api-key-content">
                    <div className="strategy-api-section">
                      <strong>Strategy methods</strong> (override these)
                      <ul>
                        <li><code>start(candle=None)</code> — called once at the beginning</li>
                        <li><code>update(open, high, low, close, index=None)</code> — called for each candle</li>
                        <li><code>end(candle=None)</code> — called once at the end</li>
                      </ul>
                    </div>
                    <div className="strategy-api-section">
                      <strong>self.stock</strong>
                      <ul>
                        <li><code>stock.symbol</code> — ticker symbol</li>
                        <li><code>stock.price(index)</code> — close price at index</li>
                        <li><code>stock.get_candle(index)</code> — (open, high, low, close)</li>
                        <li><code>stock.rsi(period=14)</code> — RSI series (list)</li>
                        <li><code>stock.sma(period=14)</code> — SMA series</li>
                        <li><code>stock.ema(period=14)</code> — EMA series</li>
                        <li><code>stock.macd(26, 12)</code> — MACD series</li>
                        <li><code>stock.bollinger_bands(20, 2)</code> — (upper, middle, lower) tuples</li>
                        <li><code>stock.atr(period=14)</code> — ATR series</li>
                        <li><code>stock.adx(period=14)</code> — ADX series</li>
                      </ul>
                    </div>
                    <div className="strategy-api-section">
                      <strong>self.portfolio</strong>
                      <ul>
                        <li><code>portfolio.cash</code> — available cash</li>
                        <li><code>portfolio.get_value(index)</code> — total portfolio value</li>
                        <li><code>portfolio.estimate_fill_price('buy'|'sell', raw_price)</code> — estimate fill w/ slippage+commission</li>
                        <li><code>portfolio.enter_position_long(stock, qty, index)</code></li>
                        <li><code>portfolio.enter_position_short(stock, qty, index)</code></li>
                        <li><code>portfolio.exit_position(stock, qty, index)</code></li>
                      </ul>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {runModalOpen && (
        <div className="strategy-run-modal-overlay" onClick={() => !running && setRunModalOpen(false)}>
          <div className="strategy-run-modal" onClick={(e) => e.stopPropagation()}>
            <div className="strategy-run-modal-header">
              <span>Run: {name || 'Strategy'}</span>
              <button type="button" className="strategy-run-modal-close" onClick={() => !running && setRunModalOpen(false)}>×</button>
            </div>
            <div className="strategy-run-modal-body">
              <div className="strategy-run-modal-section">
                <label>Stocks</label>
                {stocks.length === 0 ? (
                  <div className="strategy-run-empty">Add stocks to watchlist first</div>
                ) : (
                  <div className="strategy-run-stocks-dropdown" ref={stocksDropdownRef}>
                    <button
                      type="button"
                      className="strategy-run-stocks-trigger"
                      onClick={() => setStocksDropdownOpen((o) => !o)}
                    >
                      {runSymbols.length === 0
                        ? 'Select stocks…'
                        : runSymbols.length === 1
                          ? runSymbols[0]
                          : `${runSymbols.length} stocks selected`}
                    </button>
                    {stocksDropdownOpen && (
                      <div className="strategy-run-stocks-list">
                        {stocks.map((sym) => (
                          <label key={sym} className={`strategy-run-stock ${executingSymbols.has(sym) ? 'disabled' : ''}`}>
                            <input
                              type="checkbox"
                              checked={runSymbols.includes(sym)}
                              onChange={() => toggleRunSymbol(sym)}
                              disabled={executingSymbols.has(sym)}
                            />
                            {sym}
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
              <div className="strategy-run-modal-section">
                <label>Window</label>
                <div className="strategy-run-dates">
                  <input type="date" value={runStart} onChange={(e) => setRunStart(e.target.value)} />
                  <span>to</span>
                  <input type="date" value={runEnd} onChange={(e) => setRunEnd(e.target.value)} />
                </div>
              </div>
              <div className="strategy-run-modal-section">
                <label>Walk-forward train % (0–1, optional)</label>
                <input
                  type="number"
                  className="strategy-run-train-pct"
                  value={runTrainPct}
                  onChange={(e) => setRunTrainPct(e.target.value)}
                  placeholder="e.g. 0.7"
                  min="0"
                  max="1"
                  step="0.1"
                />
                <span className="strategy-run-hint">Split into train/test for OOS validation</span>
              </div>
              {runResults && (
                <div className="strategy-run-results">
                  {runResults.map((r, i) => (
                    <div key={i} className="strategy-run-result-row">
                      {r.error ? (
                        <span className="error">{r.symbol}: {r.error}</span>
                      ) : (
                        <>
                          <span>{r.symbol}</span>
                          <span>${r.start_value?.toFixed(0)} → ${r.end_value?.toFixed(0)}</span>
                          <span className={r.pnl >= 0 ? 'positive' : 'negative'}>
                            {r.pnl >= 0 ? '+' : ''}${r.pnl?.toFixed(2)}
                          </span>
                        </>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="strategy-run-modal-footer">
              <button type="button" className="strategy-btn" onClick={() => setRunModalOpen(false)} disabled={running}>
                Close
              </button>
              <button
                type="button"
                className="strategy-btn primary"
                onClick={handleExecute}
                disabled={running || runSymbols.length === 0}
              >
                {running ? 'Running…' : 'Execute'}
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!confirmDelete}
        title="Delete strategy"
        message={confirmDelete ? `Delete "${confirmDelete.name}"?` : ''}
        confirmLabel="Delete"
        onConfirm={doDelete}
        onCancel={() => setConfirmDelete(null)}
      />
    </div>
  )
}
