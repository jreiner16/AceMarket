// backgroundJobsStore -- track running Monte Carlo / backtest jobs for header indicator
const listeners = new Set()
let jobs = []

function emit() {
  listeners.forEach((fn) => fn(jobs))
}

export function subscribe(fn) {
  listeners.add(fn)
  fn(jobs)
  return () => listeners.delete(fn)
}

export function getJobs() {
  return jobs
}

export function addJob(job) {
  const id = job.id || `job-${Date.now()}-${Math.random().toString(36).slice(2)}`
  const entry = { id, ...job, status: job.status || 'running' }
  jobs = [...jobs, entry]
  emit()
  return id
}

export function updateJob(id, updates) {
  jobs = jobs.map((j) => (j.id === id ? { ...j, ...updates } : j))
  emit()
}

export function removeJob(id) {
  jobs = jobs.filter((j) => j.id !== id)
  emit()
}
