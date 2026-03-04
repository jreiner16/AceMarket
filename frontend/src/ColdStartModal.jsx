// ColdStartModal -- simple loading indicator when API is slow
import { useEffect, useState } from 'react'
import { subscribe } from './coldStartStore'

export function ColdStartModal() {
  const [show, setShow] = useState(false)

  useEffect(() => {
    return subscribe(setShow)
  }, [])

  if (!show) return null

  return (
    <div className="cold-start-indicator">
      <div className="cold-start-spinner" />
      <span>Loading…</span>
    </div>
  )
}
