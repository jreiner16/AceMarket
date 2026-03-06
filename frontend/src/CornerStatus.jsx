// CornerStatus -- bottom-right corner: background tasks only (cold start uses WakeUpModal)
import { useState, useEffect } from 'react'
import { subscribe as subscribeJobs } from './backgroundJobsStore'

export function CornerStatus() {
  const [jobs, setJobs] = useState([])

  useEffect(() => {
    return subscribeJobs(setJobs)
  }, [])

  if (!jobs.length) return null

  return (
    <div className="corner-status">
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
    </div>
  )
}
