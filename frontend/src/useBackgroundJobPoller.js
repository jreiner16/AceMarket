// useBackgroundJobPoller -- poll running jobs in background (Monte Carlo, backtest)
import { useEffect, useRef } from 'react'
import { getJobs, removeJob } from './backgroundJobsStore'
import { apiGet } from './apiClient'

const MAX_POLL_FAILURES = 5
const pollFailures = new Map()

function pollJob(job) {
  if (!job.job_id || job.status !== 'running') return
  const url = job.type === 'montecarlo'
    ? `/strategies/montecarlo/${job.job_id}`
    : `/strategies/run/${job.job_id}`
  return apiGet(url).then((data) => {
    pollFailures.delete(job.id)
    if (data.status === 'pending') return
    job.onComplete?.(data)
    removeJob(job.id)
  }).catch((err) => {
    const failures = (pollFailures.get(job.id) || 0) + 1
    pollFailures.set(job.id, failures)
    if (failures >= MAX_POLL_FAILURES) {
      pollFailures.delete(job.id)
      const msg = err.detail || err.message || (String(err).includes('fetch') ? 'Network error (backend may be starting)' : 'Failed')
      job.onComplete?.({ error: msg })
      removeJob(job.id)
    }
  })
}

export function useBackgroundJobPoller() {
  const intervalRef = useRef(null)

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      const jobs = getJobs().filter((j) => j.job_id && j.status === 'running')
      jobs.forEach(pollJob)
    }, 1000)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [])
}
