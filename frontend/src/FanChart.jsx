export function FanChart({ fanData, initialCash }) {
  if (!fanData?.length) return null
  const chartW = 560
  const h = 140
  const pad = { t: 8, r: 8, b: 24, l: 50 }
  const chartH = h - pad.t - pad.b
  const chartL = pad.l

  const allVals = fanData.flatMap((p) => [p.p5, p.p25, p.p50, p.p75, p.p95]).filter(Number.isFinite)
  const min = Math.min(...allVals, initialCash)
  const max = Math.max(...allVals, initialCash)
  const range = max - min || 1

  const toY = (v) => pad.t + chartH - ((Number(v) - min) / range) * chartH
  const toX = (i) => chartL + (i / Math.max(1, fanData.length - 1)) * (chartW - chartL - pad.r)

  const pts = fanData
  const p95Line = pts.map((p, i) => `${toX(i)},${toY(p.p95)}`).join(' ')
  const p5Line = pts.map((p, i) => `${toX(i)},${toY(p.p5)}`).join(' ')
  const p75Line = pts.map((p, i) => `${toX(i)},${toY(p.p75)}`).join(' ')
  const p25Line = pts.map((p, i) => `${toX(i)},${toY(p.p25)}`).join(' ')
  const p50Line = pts.map((p, i) => `${toX(i)},${toY(p.p50)}`).join(' ')

  const outerBand = p95Line + ' ' + p5Line.split(' ').reverse().join(' ')
  const innerBand = p75Line + ' ' + p25Line.split(' ').reverse().join(' ')

  const fmt = (v) => '$' + Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })
  const ticks = [max, min]
  if (range > 0) {
    const mid = min + range / 2
    if (Math.abs(mid - min) > range * 0.2) ticks.splice(1, 0, mid)
  }

  return (
    <div className="strategy-fan-chart">
      <div className="strategy-fan-chart-y-scale">
        {ticks.map((t, i) => (
          <span key={i}>{fmt(t)}</span>
        ))}
      </div>
      <svg viewBox={`0 0 ${chartW} ${h}`} preserveAspectRatio="xMidYMid meet" className="strategy-fan-chart-svg">
        <polygon points={outerBand} fill="rgba(59, 130, 246, 0.12)" stroke="none" />
        <polygon points={innerBand} fill="rgba(59, 130, 246, 0.22)" stroke="none" />
        <polyline points={p50Line} fill="none" stroke="rgb(59, 130, 246)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="strategy-fan-chart-legend">
        <span>5th–95th %ile</span>
        <span>25th–75th %ile</span>
        <span>Median</span>
      </div>
    </div>
  )
}
