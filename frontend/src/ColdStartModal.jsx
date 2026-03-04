// ColdStartModal -- shown when API is slow (e.g. server cold start)
import { useEffect, useState } from 'react'
import { subscribe } from './coldStartStore'

export function ColdStartModal() {
  const [show, setShow] = useState(false)

  useEffect(() => {
    return subscribe(setShow)
  }, [])

  if (!show) return null

  return (
    <div className="cold-start-overlay">
      <div className="cold-start-modal">
        <div className="cold-start-spinner" />
        <p className="cold-start-message">Waking up server…</p>
        <p className="cold-start-hint">This may take 30–60 seconds on first load.</p>
      </div>
    </div>
  )
}
