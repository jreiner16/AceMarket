// CornerStatus -- bottom-right corner: background tasks + API loading
import { useState, useEffect } from 'react'
import { subscribe as subscribeJobs } from './backgroundJobsStore'
import { subscribe as subscribeColdStart } from './coldStartStore'

export function CornerStatus() {
  const [jobs, setJobs] = useState([])
  const [coldStart, setColdStart] = useState(false)

  useEffect(() => {
    return subscribeJobs(setJobs)
  }, [])
  useEffect(() => {
    return subscribeColdStart(setColdStart)
  }, [])

  if (!jobs.length && !coldStart) return null

  return (
    <div className="corner-status">
      {jobs.length > 0 && (
        <div className="corner-status-tasks">
          {jobs.map((j) => (
            <div key={j.id} className="corner-status-task" title={j.message}>
              <span className="corner-status-spinner" />
              <span>
                {j.type === 'montecarlo' ? 'Monte Carlo' : 'Backtest'}
                {j.label ? ` (${j.label})` : ''}
              </span>
            </div>
          ))}
        </div>
      )}
      {coldStart && (
        <div className="corner-status-loading">
          <span className="corner-status-spinner" />
          <span>Loading…</span>
        </div>
      )}
    </div>
  )
}
