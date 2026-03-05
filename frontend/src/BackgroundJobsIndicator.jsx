// BackgroundJobsIndicator -- show running Monte Carlo / backtest in header
import { useState, useEffect } from 'react'
import { subscribe } from './backgroundJobsStore'

export function BackgroundJobsIndicator() {
  const [jobs, setJobs] = useState([])

  useEffect(() => {
    return subscribe(setJobs)
  }, [])

  if (!jobs.length) return null

  return (
    <div className="background-jobs-indicator">
      {jobs.map((j) => (
        <span key={j.id} className="background-job-pill" title={j.message}>
          <span className="background-job-spinner" />
          {j.type === 'montecarlo' ? 'Monte Carlo' : 'Backtest'}
          {j.label ? ` (${j.label})` : ''}
        </span>
      ))}
    </div>
  )
}
