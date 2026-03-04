/* apiClient --API loader */
import { auth } from './firebase'
import { onRequestStart, onRequestEnd } from './coldStartStore'

const SKIP_LOADING_PATHS = ['/strategies/montecarlo', '/strategies/run']

// Production: set VITE_API_BASE to full API URL (e.g. https://api.yoursite.com/api/v1)
const API_BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '') || '/api/v1'

async function getAuthHeaders() {
  const user = auth.currentUser
  if (!user) {
    throw new Error('Not authenticated')
  }
  const token = await user.getIdToken(true)
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  }
}

export async function apiFetch(path, options = {}) {
  const skipLoading = SKIP_LOADING_PATHS.some((p) => path.includes(p))
  onRequestStart(skipLoading)
  try {
    const url = path.startsWith('http') ? path : `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`
    const { signal, ...restOptions } = options
    const headers = {
      ...(options.headers || {}),
      ...(await getAuthHeaders()),
    }
    if (restOptions.body && typeof restOptions.body === 'object' && !(restOptions.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json'
    }
    const res = await fetch(url, { ...restOptions, headers, signal })
    if (!res.ok) {
      const err = new Error(res.statusText || `Request failed: ${res.status}`)
      err.status = res.status
      const text = await res.text()
      try {
        const data = JSON.parse(text)
        err.detail = data.detail || data.message
      } catch {
        err.detail = text
      }
      throw err
    }
    return res
  } finally {
    onRequestEnd()
  }
}

export async function apiGet(path) {
  const res = await apiFetch(path)
  return res.json()
}

export async function apiPost(path, body) {
  const res = await apiFetch(path, {
    method: 'POST',
    body: body != null ? JSON.stringify(body) : undefined,
  })
  return res.headers.get('content-length') === '0' ? null : res.json()
}

export async function apiPut(path, body) {
  const res = await apiFetch(path, {
    method: 'PUT',
    body: body != null ? JSON.stringify(body) : undefined,
  })
  return res.headers.get('content-length') === '0' ? null : res.json()
}

export async function apiDelete(path, body) {
  const res = await apiFetch(path, {
    method: 'DELETE',
    body: body != null ? JSON.stringify(body) : undefined,
  })
  return res.headers.get('content-length') === '0' ? null : res.json()
}
