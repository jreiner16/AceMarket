// StockChart -- stock candlestickchart display using lightweight-charts
import { useEffect, useRef, useState } from 'react'
import { createChart, CandlestickSeries, LineSeries } from 'lightweight-charts'
import { apiFetch } from './apiClient'

const LOAD_MORE_THRESHOLD = 50
const LOAD_MORE_CHUNK = 500

function parseDate(str) {
  if (typeof str === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(str)) {
    const [y, m, d] = str.split('-').map(Number)
    return new Date(y, m - 1, d)
  }
  return null
}

function dateBefore(dateStr) {
  const d = parseDate(dateStr)
  if (!d) return null
  d.setDate(d.getDate() - 1)
  return d.toISOString().slice(0, 10)
}

export function StockChart({ symbol, startDate, endDate, onPriceUpdate, showSma, showEma, showRsi }) {
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

    const unsubRef = { current: null }
    const stateRef = {
      loadingMore: false,
      hasMoreHistory: true,
      candleData: [],
      smaData: [],
      emaData: [],
      rsiData: [],
    }

    const applyData = (candleSeries, smaSeries, emaSeries, rsiSeries, candleData, smaData, emaData, rsiData) => {
      stateRef.candleData = candleData
      stateRef.smaData = smaData
      stateRef.emaData = emaData
      stateRef.rsiData = rsiData
      candleSeries.setData(candleData)
      if (smaSeries && smaData?.length) smaSeries.setData(smaData)
      if (emaSeries && emaData?.length) emaSeries.setData(emaData)
      if (rsiSeries && rsiData?.length) rsiSeries.setData(rsiData)
    }

    const loadMoreHistory = async (candleSeries, smaSeries, emaSeries, rsiSeries) => {
      if (!active || stateRef.loadingMore || !stateRef.hasMoreHistory) return
      const { candleData, smaData, emaData, rsiData } = stateRef
      const oldest = candleData[0]?.time
      if (!oldest) return
      const end = dateBefore(oldest)
      if (!end) return

      stateRef.loadingMore = true
      try {
        const params = new URLSearchParams()
        params.set('end_date', end)
        params.set('limit', String(LOAD_MORE_CHUNK))
        const r = await apiFetch(`/stock/${symbol}?${params}`)
        const data = await r.json()
        if (!active || !data?.candles?.length) {
          stateRef.hasMoreHistory = false
          return
        }
        const newCandles = data.candles.map((c) => ({
          time: c.time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        }))
        const newCandleData = [...newCandles, ...candleData]
        const newSmaData = showSma && data.sma?.length
          ? [
              ...(data.sma || []).map((v, i) => (v != null ? { time: newCandles[i].time, value: v } : null)).filter(Boolean),
              ...smaData,
            ]
          : smaData
        const newEmaData = showEma && data.ema?.length
          ? [
              ...(data.ema || []).map((v, i) => (v != null ? { time: newCandles[i].time, value: v } : null)).filter(Boolean),
              ...emaData,
            ]
          : emaData
        const newRsiData = showRsi && data.rsi?.length
          ? [
              ...(data.rsi || []).map((v, i) => (v != null ? { time: newCandles[i].time, value: v } : null)).filter(Boolean),
              ...rsiData,
            ]
          : rsiData
        applyData(candleSeries, smaSeries, emaSeries, rsiSeries, newCandleData, newSmaData, newEmaData, newRsiData)
        if (data.candles.length < LOAD_MORE_CHUNK) stateRef.hasMoreHistory = false
      } finally {
        stateRef.loadingMore = false
      }
    }

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

        let smaSeries = null
        let smaData = []
        let emaSeries = null
        let emaData = []
        let rsiSeries = null
        let rsiData = []

        if (showSma && (data.sma || []).length) {
          smaData = candleData
            .map((c, i) => (data.sma[i] != null ? { time: c.time, value: data.sma[i] } : null))
            .filter(Boolean)
          if (smaData.length) {
            smaSeries = chart.addSeries(LineSeries, { color: '#f97316', lineWidth: 2, title: 'SMA(14)' })
          }
        }
        if (showEma && (data.ema || []).length) {
          emaData = candleData
            .map((c, i) => (data.ema[i] != null ? { time: c.time, value: data.ema[i] } : null))
            .filter(Boolean)
          if (emaData.length) {
            emaSeries = chart.addSeries(LineSeries, { color: '#06b6d4', lineWidth: 2, title: 'EMA(14)' })
          }
        }
        if (showRsi && (data.rsi || []).length) {
          rsiData = candleData
            .map((c, i) => (data.rsi[i] != null ? { time: c.time, value: data.rsi[i] } : null))
            .filter(Boolean)
          if (rsiData.length) {
            rsiSeries = chart.addSeries(
              LineSeries,
              { color: '#a855f7', lineWidth: 2, title: 'RSI(14)', priceScaleId: 'rsi' },
              1
            )
            rsiSeries.priceScale().applyOptions({ scaleMargins: { top: 0.1, bottom: 0.1 }, borderVisible: true })
          }
        }

        applyData(candleSeries, smaSeries, emaSeries, rsiSeries, candleData, smaData, emaData, rsiData)

        unsubRef.current = chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
          if (!range || range.from == null) return
          if (range.from < LOAD_MORE_THRESHOLD) {
            loadMoreHistory(candleSeries, smaSeries, emaSeries, rsiSeries)
          }
        })

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
      unsubRef.current?.()
      resizeObserver.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [symbol, startDate, endDate, onPriceUpdate, showSma, showEma, showRsi])

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
