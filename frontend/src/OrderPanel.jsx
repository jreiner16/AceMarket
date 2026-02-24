// OrderPanel -- menu for buying and selling stocks
import { useState } from 'react'
import { apiPost } from './apiClient'

export function OrderPanel({ symbol, price, onOrder }) {
  const [quantity, setQuantity] = useState('')
  const [loading, setLoading] = useState(false)

  const handleOrder = async (side) => {
    const qty = parseInt(quantity, 10)
    if (!qty || qty <= 0) return
    setLoading(true)
    try {
      await apiPost('/portfolio/position', { symbol, quantity: qty, side })
      setQuantity('')
      onOrder?.()
    } catch (err) {
      console.error('Order:', err.detail || err.message || 'Order failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="order-panel">
      <div className="order-panel-header">
        <span className="order-panel-title">Order</span>
      </div>
      {symbol ? (
        <>
          <div className="order-panel-symbol">{symbol}</div>
          {price != null && (
            <div className="order-panel-price">
              Last: ${price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </div>
          )}
          <input
            type="number"
            className="order-input"
            placeholder="Quantity"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value.replace(/\D/g, ''))}
            min="1"
          />
          <div className="order-buttons">
            <button
              className="order-btn long"
              onClick={() => handleOrder('long')}
              disabled={loading || !quantity}
            >
              Buy Long
            </button>
            <button
              className="order-btn short"
              onClick={() => handleOrder('short')}
              disabled={loading || !quantity}
            >
              Sell Short
            </button>
          </div>
        </>
      ) : (
        <div className="order-panel-empty">Select a symbol</div>
      )}
    </div>
  )
}
