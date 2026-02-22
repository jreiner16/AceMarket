import { useEffect, useRef, useState } from 'react'
import { createChart, CandlestickSeries } from 'lightweight-charts'
import { apiFetch } from './apiClient'

export function StockChart({ symbol, startDate, endDate, onPriceUpdate }) {
  const chartContainerRef = useRef(null)
  const chartRef = useRef(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!symbol || !chartContainerRef.current) return

    let active = true
    const controller = new AbortController()
    const initTimer = setTimeout(() => {
      if (!active) return
      setLoading(true)
      setError(null)
    }, 0)

    const font = 'Tahoma, Verdana, Arial, sans-serif'
    const container = chartContainerRef.current
    const chart = createChart(container, {
      layout: {
        background: { color: '#0f0f0f' },
        textColor: '#888',
        fontFamily: font,
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: '#1a1a1a' },
        horzLines: { color: '#1a1a1a' },
      },
      crosshair: {
        mode: 1,
        vertLine: {
          color: '#525252',
          width: 1,
          style: 2,
          labelBackgroundColor: '#262626',
        },
        horzLine: {
          color: '#525252',
          width: 1,
          style: 2,
          labelBackgroundColor: '#262626',
        },
      },
      rightPriceScale: {
        borderColor: '#2a2a2a',
        scaleMargins: { top: 0.1, bottom: 0.2 },
      },
      timeScale: {
        borderColor: '#2a2a2a',
        timeVisible: true,
        secondsVisible: false,
      },
    })

    chartRef.current = chart

    const resizeObserver = new ResizeObserver((entries) => {
      if (chartRef.current && entries[0]) {
        const { width, height } = entries[0].contentRect
        chartRef.current.applyOptions({ width, height })
      }
    })
    resizeObserver.observe(container)

    const params = new URLSearchParams()
    if (startDate) params.set('start_date', startDate)
    if (endDate) params.set('end_date', endDate)
    apiFetch(`/stock/${symbol}?${params}`, { signal: controller.signal })
      .then((r) => r.json())
      .then((data) => {
        if (!active) return
        if (!data?.candles?.length) throw new Error('No chart data')
        const candleData = data.candles.map((c) => ({
          time: c.time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        }))

        const candleSeries = chart.addSeries(CandlestickSeries, {
          upColor: '#22c55e',
          downColor: '#ef4444',
          borderUpColor: '#22c55e',
          borderDownColor: '#ef4444',
          wickUpColor: '#22c55e',
          wickDownColor: '#ef4444',
        })
        candleSeries.setData(candleData)
        chart.timeScale().fitContent()

        const lastCandle = candleData[candleData.length - 1]
        if (lastCandle && onPriceUpdate) {
          onPriceUpdate(lastCandle.close)
        }
        setLoading(false)
      })
      .catch((err) => {
        if (err?.name === 'AbortError') return
        if (!active) return
        setError(err.message || 'Failed to load chart')
        setLoading(false)
      })

    return () => {
      active = false
      clearTimeout(initTimer)
      controller.abort()
      resizeObserver.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [symbol, startDate, endDate, onPriceUpdate])

  return (
    <div className="chart-shell">
      <div ref={chartContainerRef} className="chart-shell-inner" />
      {loading && (
        <div className="chart-overlay">
          <span>Loading {symbol}…</span>
        </div>
      )}
      {error && (
        <div className="chart-overlay">
          <span className="chart-overlay-error">{error}</span>
          <span className="chart-overlay-hint">This symbol might not exist, or it may not be supported by the backend.</span>
        </div>
      )}
    </div>
  )
}
