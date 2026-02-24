/**
 * API client loader
 */
import { auth } from './firebase'

const API_BASE = '/api/v1'

async function getAuthHeaders() {
  const user = auth.currentUser
  if (!user) {
    throw new Error('Not authenticated')
  }
  const token = await user.getIdToken()
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  }
}

export async function apiFetch(path, options = {}) {
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
    try {
      const data = await res.json()
      err.detail = data.detail || data.message
    } catch {
      err.detail = await res.text()
    }
    throw err
  }
  return res
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
