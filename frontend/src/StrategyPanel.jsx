// StrategyPanel -- create/run strategies with custom python framework
import { useState, useEffect, useCallback, useRef } from 'react'
import Editor from 'react-simple-code-editor'
import { highlight, languages } from 'prismjs'
import 'prismjs/components/prism-python'
import { ResizeHandle } from './ResizeHandle'
import { ConfirmDialog } from './ConfirmDialog'
import { FanChart } from './FanChart'
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
            shares = self.portfolio.max_affordable_buy(close, reserve_fraction=0.05)
            if shares > 0:
                self.portfolio.enter_position_long(self.stock, shares, index)

        # Death cross: short crosses below long -> sell
        elif in_position and qty > 0 and prev_short >= prev_long and short < long_val:
            self.portfolio.exit_position(self.stock, qty, index)

    def end(self, candle=None):
        """Called once at the end of the backtest."""
        pass
`

export function StrategyPanel({ watchlist, refresh, onRefresh, onRunCompleted, compact }) {
  const [strategies, setStrategies] = useState([])
  const [selected, setSelected] = useState(null)
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [runModalOpen, setRunModalOpen] = useState(false)
  const [runMode, setRunMode] = useState('backtest')  // 'backtest' | 'montecarlo'
  const [runSymbols, setRunSymbols] = useState([])
  const [runMonteCarloSymbol, setRunMonteCarloSymbol] = useState('')
  const [runMonteCarloSims, setRunMonteCarloSims] = useState('100')
  const [runMonteCarloHorizon, setRunMonteCarloHorizon] = useState('252')
  const [stocksDropdownOpen, setStocksDropdownOpen] = useState(false)
  const [runStart, setRunStart] = useState('2023-01-01')
  const [runEnd, setRunEnd] = useState('2024-01-01')
  const [runTrainPct, setRunTrainPct] = useState('')  // e.g. 0.7 for 70% train, 30% OOS test
  const [runResults, setRunResults] = useState(null)
  const [monteCarloResults, setMonteCarloResults] = useState(null)
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
      const msg = e.detail || e.message || 'Failed to save'
      console.error('Strategy:', msg)
      if (String(msg).includes('Lookahead blocked')) {
        console.error('Lookahead violation: strategy code cannot access stock.df, .iloc, .loc, etc.')
      }
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
    setMonteCarloResults(null)
    setStocksDropdownOpen(false)
  }

  const toggleRunSymbol = (sym) => {
    if (executingSymbols.has(sym)) return
    setRunSymbols((prev) =>
      prev.includes(sym) ? prev.filter((s) => s !== sym) : [...prev, sym]
    )
  }

  const handleExecute = async () => {
    if (runMode === 'montecarlo') {
      const sym = runMonteCarloSymbol?.trim().toUpperCase()
      if (!sym) {
        console.error('Strategy: Select a stock for Monte Carlo')
        return
      }
      setRunning(true)
      setMonteCarloResults(null)
      setExecutingSymbols(new Set([sym]))
      try {
        const n = Math.max(10, Math.min(500, parseInt(runMonteCarloSims, 10) || 100))
        const h = Math.max(21, Math.min(504, parseInt(runMonteCarloHorizon, 10) || 252))
        const data = await apiPost('/strategies/montecarlo', {
          strategy_id: selected,
          symbol: sym,
          n_sims: n,
          horizon: h,
        })
        setMonteCarloResults(data)
        onRefresh?.()
        if (data?.run_id != null) onRunCompleted?.(data.run_id)
      } catch (e) {
        setMonteCarloResults({ error: e.detail || e.message })
      } finally {
        setRunning(false)
        setExecutingSymbols(new Set())
      }
      return
    }

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
      if (data?.run_id != null) onRunCompleted?.(data.run_id)
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
                      <strong>Class structure</strong>
                      <ul>
                        <li>Define one class inheriting from <code>Strategy</code></li>
                        <li><code>def __init__(self, stock, portfolio, my_param=10):</code> — first two args required; custom params need defaults</li>
                        <li>Call <code>super().__init__()</code>; base sets <code>self.stock</code>, <code>self.portfolio</code></li>
                      </ul>
                    </div>
                    <div className="strategy-api-section">
                      <strong>Lifecycle methods</strong> (override these)
                      <ul>
                        <li><code>start(self, candle=None)</code> — called once at backtest start</li>
                        <li><code>update(self, open, high, low, close, index=None)</code> — called every bar. <code>open, high, low, close</code> = OHLC for current bar. <code>index</code> = bar index (0-based). Only use data at or before <code>index</code>.</li>
                        <li><code>end(self, candle=None)</code> — called once at backtest end</li>
                      </ul>
                    </div>
                    <div className="strategy-api-section">
                      <strong>self.stock</strong> — price & candles
                      <ul>
                        <li><code>stock.symbol</code> — ticker string</li>
                        <li><code>stock.price(index)</code> → float, close at bar <code>index</code></li>
                        <li><code>stock.get_candle(index)</code> → (open, high, low, close) tuple</li>
                        <li><code>stock.to_iloc(index)</code> → int, convert date string or int to bar index</li>
                      </ul>
                    </div>
                    <div className="strategy-api-section">
                      <strong>self.stock</strong> — indicators (return lists; index with <code>[index]</code>; check <code>index &lt; len(series)</code> and <code>series[index] is not None</code>)
                      <ul>
                        <li><code>stock.sma(period=14)</code> — Simple Moving Average</li>
                        <li><code>stock.ema(period=14)</code> — Exponential Moving Average</li>
                        <li><code>stock.rsi(period=14)</code> — RSI (0–100)</li>
                        <li><code>stock.atr(period=14)</code> — Average True Range</li>
                        <li><code>stock.adx(period=14)</code> — ADX</li>
                        <li><code>stock.macd(long_period=26, short_period=12)</code> — MACD line</li>
                        <li><code>stock.bollinger_bands(period=20, dev=2)</code> → list of (upper, middle, lower) tuples per bar</li>
                        <li><code>stock.tr(index)</code> → float, True Range at bar</li>
                        <li><code>stock.dm()</code> → (plus_dm_list, minus_dm_list)</li>
                      </ul>
                    </div>
                    <div className="strategy-api-section">
                      <strong>self.portfolio</strong>
                      <ul>
                        <li><code>portfolio.cash</code> — available cash (float)</li>
                        <li><code>portfolio.get_value(index)</code> — total equity at bar</li>
                        <li><code>portfolio.get_position(stock)</code> — dict with <code>quantity</code>, <code>avg_price</code>, etc., or None</li>
                        <li><code>portfolio.stocks</code> — list of (stock, qty) tuples for current positions</li>
                        <li><code>portfolio.estimate_fill_price('buy', price)</code> or <code>('sell', price)</code> — fill price with slippage</li>
                        <li><code>portfolio.estimate_buy_cost(qty, price)</code> — total cost (fill + commission); use for cash checks</li>
                        <li><code>portfolio.max_affordable_buy(price, reserve_fraction=0.05)</code> — max qty affordable with 95% of cash</li>
                        <li><code>portfolio.enter_position_long(stock, qty, index)</code> — open or add to long</li>
                        <li><code>portfolio.enter_position_short(stock, qty, index)</code> — open or add to short</li>
                        <li><code>portfolio.exit_position(stock, qty, index)</code> — close qty shares; qty must ≤ position size</li>
                      </ul>
                    </div>
                    <div className="strategy-api-section">
                      <strong>Forbidden</strong> (lookahead blocked)
                      <ul>
                        <li>No <code>stock.df</code>, <code>stock.df.iloc</code>, <code>.loc</code>, <code>.iat</code>, <code>.at</code>, <code>.values</code>, <code>.index</code></li>
                        <li>Use <code>stock.price(index)</code>, <code>stock.get_candle(index)</code>, <code>stock.sma(14)[index]</code> instead</li>
                      </ul>
                    </div>
                    <div className="strategy-api-section">
                      <strong>Forbidden Python</strong>
                      <ul>
                        <li>No <code>import</code> or <code>from ... import</code></li>
                        <li>No <code>global</code>, <code>nonlocal</code></li>
                        <li>No <code>eval</code>, <code>exec</code>, <code>open</code>, <code>input</code>, <code>getattr</code>, <code>setattr</code>, <code>type</code>, <code>isinstance</code>, <code>hasattr</code>, <code>repr</code>, <code>format</code>, <code>bytes</code>, <code>bytearray</code></li>
                      </ul>
                    </div>
                    <div className="strategy-api-section">
                      <strong>Allowed builtins</strong>
                      <ul>
                        <li><code>range</code>, <code>len</code>, <code>min</code>, <code>max</code>, <code>sum</code>, <code>abs</code>, <code>round</code>, <code>int</code>, <code>float</code>, <code>str</code>, <code>bool</code>, <code>list</code>, <code>dict</code>, <code>set</code>, <code>tuple</code>, <code>enumerate</code>, <code>zip</code>, <code>next</code>, <code>any</code>, <code>all</code>, <code>sorted</code>, <code>super</code>, <code>Exception</code>, <code>ValueError</code>, <code>TypeError</code>, <code>print</code></li>
                      </ul>
                    </div>
                    <div className="strategy-api-section">
                      <strong>Common mistakes</strong>
                      <ul>
                        <li>Index out of range: always check <code>index &lt; len(series)</code> and <code>series[index] is not None</code> before using indicators</li>
                        <li>Always pass <code>index</code> to <code>enter_position_long</code>, <code>enter_position_short</code>, <code>exit_position</code></li>
                        <li>ATR/RSI can be 0 or None — guard divisions with checks</li>
                        <li><code>exit_position(stock, qty, index)</code> — qty must not exceed position size</li>
                      </ul>
                    </div>
                    <div className="strategy-api-section">
                      <strong>Limits</strong>
                      <ul>
                        <li>Code max 50,000 chars; init timeout 30s; strategy name unique and non-empty</li>
                      </ul>
                    </div>
                    <div className="strategy-api-section">
                      <strong>Example</strong> — ATR-based entry with bounds check:
                      <pre className="strategy-api-example">{`atr_series = self.stock.atr(14)
if index < len(atr_series) and atr_series[index]:
    atr = atr_series[index]
    qty = int(self.portfolio.get_value(index) * 0.01 / atr)
    if qty > 0 and self.position is None:
        self.portfolio.enter_position_long(self.stock, qty, index)
        self.position = qty`}</pre>
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
                <label>Mode</label>
                <div className="strategy-run-mode-toggle">
                  <button
                    type="button"
                    className={`strategy-run-mode-btn ${runMode === 'backtest' ? 'active' : ''}`}
                    onClick={() => { setRunMode('backtest'); setRunResults(null); setMonteCarloResults(null); }}
                  >
                    Backtest (historical)
                  </button>
                  <button
                    type="button"
                    className={`strategy-run-mode-btn ${runMode === 'montecarlo' ? 'active' : ''}`}
                    onClick={() => { setRunMode('montecarlo'); setRunResults(null); setMonteCarloResults(null); }}
                  >
                    Monte Carlo (future)
                  </button>
                </div>
                <span className="strategy-run-hint">
                  {runMode === 'backtest' ? 'Run on past data' : 'Sample from historical returns, simulate many future paths'}
                </span>
              </div>

              {runMode === 'montecarlo' ? (
                <>
                  <div className="strategy-run-modal-section">
                    <label>Stock</label>
                    {stocks.length === 0 ? (
                      <div className="strategy-run-empty">Add stocks to watchlist first</div>
                    ) : (
                      <div className="strategy-run-stocks-dropdown" ref={stocksDropdownRef}>
                        <button
                          type="button"
                          className="strategy-run-stocks-trigger"
                          onClick={() => setStocksDropdownOpen((o) => !o)}
                          disabled={running}
                        >
                          {runMonteCarloSymbol || 'Select stock…'}
                        </button>
                        {stocksDropdownOpen && (
                          <div className="strategy-run-stocks-list">
                            {stocks.map((sym) => (
                              <div
                                key={sym}
                                className={`strategy-run-stock ${executingSymbols.has(sym) ? 'disabled' : ''} ${runMonteCarloSymbol === sym ? 'selected' : ''}`}
                                onClick={() => {
                                  if (!executingSymbols.has(sym)) {
                                    setRunMonteCarloSymbol(sym)
                                    setStocksDropdownOpen(false)
                                  }
                                }}
                              >
                                {sym}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="strategy-run-modal-section">
                    <label>Simulations</label>
                    <input
                      type="number"
                      className="strategy-run-train-pct"
                      value={runMonteCarloSims}
                      onChange={(e) => setRunMonteCarloSims(e.target.value)}
                      min="10"
                      max="500"
                      placeholder="100"
                    />
                    <span className="strategy-run-hint">10–500 paths (default 100)</span>
                  </div>
                  <div className="strategy-run-modal-section">
                    <label>Horizon (trading days)</label>
                    <input
                      type="number"
                      className="strategy-run-train-pct"
                      value={runMonteCarloHorizon}
                      onChange={(e) => setRunMonteCarloHorizon(e.target.value)}
                      min="21"
                      max="504"
                      placeholder="252"
                    />
                    <span className="strategy-run-hint">~1 year = 252 days</span>
                  </div>
                </>
              ) : (
                <>
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
                </>
              )}

              {monteCarloResults && !monteCarloResults.error && (
                <div className="strategy-run-results strategy-run-montecarlo-results">
                  {monteCarloResults.fan_data?.length > 1 && (
                    <div className="strategy-run-fan-chart-wrap">
                      <FanChart fanData={monteCarloResults.fan_data} initialCash={monteCarloResults.initial_cash} />
                    </div>
                  )}
                  <div className="strategy-run-result-row">
                    <span><strong>Prob. profitable:</strong></span>
                    <span>{monteCarloResults.prob_profit_pct?.toFixed(1)}%</span>
                  </div>
                  <div className="strategy-run-result-row">
                    <span><strong>Mean end value:</strong></span>
                    <span>${monteCarloResults.mean?.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                  </div>
                  <div className="strategy-run-result-row">
                    <span><strong>5th %ile:</strong></span>
                    <span>${monteCarloResults.percentiles?.p5?.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                  </div>
                  <div className="strategy-run-result-row">
                    <span><strong>50th %ile:</strong></span>
                    <span>${monteCarloResults.percentiles?.p50?.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                  </div>
                  <div className="strategy-run-result-row">
                    <span><strong>95th %ile:</strong></span>
                    <span>${monteCarloResults.percentiles?.p95?.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                  </div>
                  <div className="strategy-run-result-row strategy-run-montecarlo-meta">
                    <span>{monteCarloResults.n_success} paths, {monteCarloResults.horizon} days each</span>
                  </div>
                </div>
              )}
              {monteCarloResults?.error && (
                <div className="strategy-run-results">
                  <div className="strategy-run-result-row"><span className="error">{monteCarloResults.error}</span></div>
                </div>
              )}
              {runResults && runMode === 'backtest' && (
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
                disabled={running || (runMode === 'backtest' ? runSymbols.length === 0 : !runMonteCarloSymbol?.trim())}
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
