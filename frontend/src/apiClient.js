/* apiClient --API loader */
import { auth } from './firebase'
import { onRequestStart, onRequestEnd } from './coldStartStore'

const SKIP_LOADING_PATHS = ['/strategies/montecarlo', '/strategies/run']

// Stock chart cache: key -> { ts, data }. TTL 5 min. Switching symbols is instant when cached.
const STOCK_CACHE_TTL_MS = 5 * 60 * 1000
const stockCache = new Map()
const STOCK_CACHE_MAX = 20

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
  const isStockGet = options.method !== 'POST' && options.method !== 'PUT' && options.method !== 'DELETE' && path.includes('/stock/')
  const cacheKey = isStockGet ? path : null

  if (cacheKey) {
    const now = Date.now()
    const hit = stockCache.get(cacheKey)
    if (hit && now - hit.ts < STOCK_CACHE_TTL_MS) {
      return new Response(JSON.stringify(hit.data), { headers: { 'Content-Type': 'application/json' } })
    }
  }

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

    if (cacheKey) {
      const data = await res.clone().json()
      const now = Date.now()
      if (stockCache.size >= STOCK_CACHE_MAX) {
        const oldest = [...stockCache.entries()].sort((a, b) => a[1].ts - b[1].ts)[0]
        if (oldest) stockCache.delete(oldest[0])
      }
      stockCache.set(cacheKey, { ts: now, data })
      return res
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
