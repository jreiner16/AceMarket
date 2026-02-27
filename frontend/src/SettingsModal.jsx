// SettingsModal -- popup for user settings like fees, trade limits, etc
import { useState, useEffect } from 'react'
import { ConfirmDialog } from './ConfirmDialog'
import { apiGet, apiPut, apiPost } from './apiClient'

export function SettingsModal({ open, onClose, onClearHistory, user }) {
  const [tab, setTab] = useState('order')
  const [initialCash, setInitialCash] = useState('100000')
  const [slippage, setSlippage] = useState('0')
  const [commission, setCommission] = useState('0')
  const [commissionPerOrder, setCommissionPerOrder] = useState('0')
  const [commissionPerShare, setCommissionPerShare] = useState('0')
  const [allowShort, setAllowShort] = useState(true)
  const [maxPositions, setMaxPositions] = useState('0')
  const [maxPositionPct, setMaxPositionPct] = useState('0')
  const [minCashReservePct, setMinCashReservePct] = useState('0')
  const [minTradeValue, setMinTradeValue] = useState('0')
  const [maxTradeValue, setMaxTradeValue] = useState('0')
  const [maxOrderQty, setMaxOrderQty] = useState('0')
  const [shareMinPct, setShareMinPct] = useState('10')
  const [shortMarginRequirement, setShortMarginRequirement] = useState('1.5')
  const [autoLiquidateEnd, setAutoLiquidateEnd] = useState(true)
  const [blockLookahead, setBlockLookahead] = useState(true)
  const [confirmClear, setConfirmClear] = useState(false)

  useEffect(() => {
    if (open) {
      setTab('order')
      apiGet('/settings')
        .then((s) => {
          setInitialCash(String(s.initial_cash ?? 100000))
          setSlippage(String(s.slippage ?? 0))
          setCommission(String(s.commission ?? 0))
          setCommissionPerOrder(String(s.commission_per_order ?? 0))
          setCommissionPerShare(String(s.commission_per_share ?? 0))
          setAllowShort(Boolean(s.allow_short ?? true))
          setMaxPositions(String(s.max_positions ?? 0))
          setMaxPositionPct(String(s.max_position_pct ?? 0))
          setMinCashReservePct(String(s.min_cash_reserve_pct ?? 0))
          setMinTradeValue(String(s.min_trade_value ?? 0))
          setMaxTradeValue(String(s.max_trade_value ?? 0))
          setMaxOrderQty(String(s.max_order_qty ?? 0))
          setShareMinPct(String(s.share_min_pct ?? (s.share_precision != null ? [100, 10, 1][Math.min(s.share_precision, 2)] : 10)))
          setShortMarginRequirement(String(s.short_margin_requirement ?? 1.5))
          setAutoLiquidateEnd(Boolean(s.auto_liquidate_end ?? true))
          setBlockLookahead(Boolean(s.block_lookahead ?? true))
        })
    }
  }, [open])

  const handleSave = async () => {
    try {
      const ic = Number(initialCash)
      const c = Number(commission)
      const mp = Number.parseInt(maxPositions, 10)
      const mpp = Number(maxPositionPct)
      const reserve = Number(minCashReservePct)
      const minTv = Number(minTradeValue)
      const maxTv = Number(maxTradeValue)
      const moq = Number.parseInt(maxOrderQty, 10)
      const smr = Number(shortMarginRequirement)

      const s = Number(slippage)
      const cpo = Number(commissionPerOrder)
      const cps = Number(commissionPerShare)
      await apiPut('/settings', {
        initial_cash: Number.isFinite(ic) ? ic : 100000,
        slippage: Number.isFinite(s) ? s : 0,
        commission: Number.isFinite(c) ? c : 0,
        commission_per_order: Number.isFinite(cpo) ? cpo : 0,
        commission_per_share: Number.isFinite(cps) ? cps : 0,
        allow_short: Boolean(allowShort),
        max_positions: Number.isFinite(mp) ? mp : 0,
        max_position_pct: Number.isFinite(mpp) ? mpp : 0,
        min_cash_reserve_pct: Number.isFinite(reserve) ? reserve : 0,
        min_trade_value: Number.isFinite(minTv) ? minTv : 0,
        max_trade_value: Number.isFinite(maxTv) ? maxTv : 0,
        max_order_qty: Number.isFinite(moq) ? moq : 0,
        share_min_pct: Math.max(1, Math.min(100, Number(shareMinPct) || 10)),
        short_margin_requirement: Number.isFinite(smr) ? smr : 1.5,
        auto_liquidate_end: Boolean(autoLiquidateEnd),
        block_lookahead: Boolean(blockLookahead),
      })
      onClose()
    } catch (err) {
      console.error('Settings:', err.message || 'Failed to save settings')
    }
  }

  if (!open) return null

  return (
    <div className="settings-modal" onClick={onClose}>
      <div className="settings-content" onClick={(e) => e.stopPropagation()}>
        <div className="settings-header">
          <div className="settings-title">Settings</div>
          <div className="settings-tabs">
            <button type="button" className={tab === 'order' ? 'active' : ''} onClick={() => setTab('order')}>Order</button>
            <button type="button" className={tab === 'account' ? 'active' : ''} onClick={() => setTab('account')}>Account</button>
            <button type="button" className={tab === 'risk' ? 'active' : ''} onClick={() => setTab('risk')}>Risk</button>
            <button type="button" className={tab === 'backtest' ? 'active' : ''} onClick={() => setTab('backtest')}>Backtest</button>
          </div>
        </div>

        <div className="settings-body">
          {tab === 'order' && (
            <div className="settings-tab-content">
              <fieldset className="settings-group">
                <legend>Fees</legend>
                <div className="settings-row">
                  <label className="settings-label">Slippage (decimal, e.g. 0.001 = 0.1%)</label>
                  <input type="number" className="settings-input" value={slippage} onChange={(e) => setSlippage(e.target.value)} min="0" max="0.999" step="0.001" placeholder="e.g. 0.001" />
                </div>
                <div className="settings-row">
                  <label className="settings-label">Commission % of notional (0–1)</label>
                  <input type="number" className="settings-input" value={commission} onChange={(e) => setCommission(e.target.value)} min="0" max="0.999" step="0.001" />
                </div>
                <div className="settings-row">
                  <label className="settings-label">Commission $ per order</label>
                  <input type="number" className="settings-input" value={commissionPerOrder} onChange={(e) => setCommissionPerOrder(e.target.value)} min="0" step="0.01" />
                </div>
                <div className="settings-row">
                  <label className="settings-label">Commission $ per share</label>
                  <input type="number" className="settings-input" value={commissionPerShare} onChange={(e) => setCommissionPerShare(e.target.value)} min="0" step="0.001" />
                </div>
                <div className="settings-hint">Per-order and per-share override % if set.</div>
              </fieldset>
              <fieldset className="settings-group">
                <legend>Trade Limits</legend>
                <div className="settings-row">
                  <label className="settings-label">Min Trade Value ($)</label>
                  <input type="number" className="settings-input" value={minTradeValue} onChange={(e) => setMinTradeValue(e.target.value)} min="0" step="10" />
                </div>
                <div className="settings-row">
                  <label className="settings-label">Max Trade Value ($, 0=unlimited)</label>
                  <input type="number" className="settings-input" value={maxTradeValue} onChange={(e) => setMaxTradeValue(e.target.value)} min="0" step="100" />
                </div>
                <div className="settings-row">
                  <label className="settings-label">Max Order Qty (0=unlimited)</label>
                  <input type="number" className="settings-input" value={maxOrderQty} onChange={(e) => setMaxOrderQty(e.target.value)} min="0" step="1" />
                </div>
                <div className="settings-row">
                  <label className="settings-label">Min share increment (%) — 100=whole, 10=0.1, 1=0.01</label>
                  <input type="number" className="settings-input" value={shareMinPct} onChange={(e) => setShareMinPct(e.target.value)} min="1" max="100" step="1" placeholder="10" />
                </div>
              </fieldset>
            </div>
          )}

          {tab === 'account' && (
            <div className="settings-tab-content">
              {user && (
                <fieldset className="settings-group">
                  <legend>Your account</legend>
                  <div className="settings-row">
                    <label className="settings-label">Email</label>
                    <input type="text" className="settings-input" value={user.email || ''} readOnly disabled />
                  </div>
                </fieldset>
              )}
              <fieldset className="settings-group">
                <legend>Paper trading</legend>
                <div className="settings-row">
                  <label className="settings-label">Initial Cash ($)</label>
                  <input type="number" className="settings-input" value={initialCash} onChange={(e) => setInitialCash(e.target.value)} min="0" step="1000" />
                </div>
                <div className="settings-row settings-row-inline">
                  <label className="settings-check">
                    <input type="checkbox" checked={allowShort} onChange={(e) => setAllowShort(e.target.checked)} />
                    Allow Short Selling
                  </label>
                </div>
              </fieldset>
              <div className="settings-row">
                <button
                  type="button"
                  className="settings-clear-btn"
                  onClick={() => setConfirmClear(true)}
                >
                  Clear history
                </button>
              </div>
            </div>
          )}

          {tab === 'risk' && (
            <div className="settings-tab-content">
              <fieldset className="settings-group">
                <legend>Risk Limits</legend>
                <div className="settings-row">
                  <label className="settings-label">Max Positions (0=unlimited)</label>
                  <input type="number" className="settings-input" value={maxPositions} onChange={(e) => setMaxPositions(e.target.value)} min="0" step="1" />
                </div>
                <div className="settings-row">
                  <label className="settings-label">Max Position % of Equity (0–1, 0=off)</label>
                  <input type="number" className="settings-input" value={maxPositionPct} onChange={(e) => setMaxPositionPct(e.target.value)} min="0" max="1" step="0.01" />
                </div>
                <div className="settings-row">
                  <label className="settings-label">Min Cash Reserve % (0–1)</label>
                  <input type="number" className="settings-input" value={minCashReservePct} onChange={(e) => setMinCashReservePct(e.target.value)} min="0" max="1" step="0.01" />
                </div>
                <div className="settings-row">
                  <label className="settings-label">Short Margin Requirement (1–3)</label>
                  <input type="number" className="settings-input" value={shortMarginRequirement} onChange={(e) => setShortMarginRequirement(e.target.value)} min="1" max="3" step="0.1" />
                </div>
              </fieldset>
            </div>
          )}

          {tab === 'backtest' && (
            <div className="settings-tab-content">
              <fieldset className="settings-group">
                <legend>Backtests</legend>
                <div className="settings-row settings-row-inline">
                  <label className="settings-check">
                    <input type="checkbox" checked={autoLiquidateEnd} onChange={(e) => setAutoLiquidateEnd(e.target.checked)} />
                    Auto-liquidate at end of each symbol
                  </label>
                </div>
                <div className="settings-hint">
                  This prevents multi-symbol runs from getting stuck with open positions (and “not enough cash”).
                </div>
                <div className="settings-row settings-row-inline">
                  <label className="settings-check">
                    <input type="checkbox" checked={blockLookahead} onChange={(e) => setBlockLookahead(e.target.checked)} />
                    Block lookahead (prevent cheating)
                  </label>
                </div>
                <div className="settings-hint">
                  When on, strategy code cannot access stock.df, .iloc, .loc, etc. Violations appear in the Console.
                </div>
              </fieldset>
            </div>
          )}
        </div>

        <div className="settings-actions">
          <button className="settings-cancel" onClick={onClose}>Cancel</button>
          <button className="settings-save" onClick={handleSave}>Save</button>
        </div>
      </div>

      <ConfirmDialog
        open={confirmClear}
        title="Clear history"
        message="Clear all history and reset portfolio?"
        confirmLabel="Clear"
        onConfirm={async () => {
          setConfirmClear(false)
          try {
            await apiPost('/portfolio/clear')
            onClearHistory?.()
            onClose()
          } catch (e) {
            console.error('Settings:', e.detail || e.message || 'Failed to clear history')
          }
        }}
        onCancel={() => setConfirmClear(false)}
      />
    </div>
  )
}
