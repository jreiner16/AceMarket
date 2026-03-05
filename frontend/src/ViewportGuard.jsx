// ViewportGuard -- popup when mobile or bad aspect ratio
import { useState, useEffect } from 'react'

const MIN_WIDTH = 900
const MIN_WIDTH_PORTRAIT = 768

export function ViewportGuard() {
  const [show, setShow] = useState(false)

  useEffect(() => {
    const check = () => {
      const w = window.innerWidth
      const h = window.innerHeight
      const isNarrow = w < MIN_WIDTH
      const isPortraitNarrow = h > w && w < MIN_WIDTH_PORTRAIT
      setShow(isNarrow || isPortraitNarrow)
    }
    check()
    window.addEventListener('resize', check)
    return () => window.removeEventListener('resize', check)
  }, [])

  if (!show) return null

  return (
    <div className="viewport-guard" role="alert">
      <div className="viewport-guard-card">
        <div className="viewport-guard-icon">⊞</div>
        <h2 className="viewport-guard-title">Best on desktop</h2>
        <p className="viewport-guard-text">
          AceMarket works best on a larger screen. Use a desktop or laptop, or rotate your device to landscape.
        </p>
      </div>
    </div>
  )
}
