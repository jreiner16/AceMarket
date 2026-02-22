/**
 * Unit tests for apiClient.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { apiGet, apiPost, apiDelete } from './apiClient'

// Mock Firebase auth
vi.mock('./firebase', () => ({
  auth: {
    currentUser: { getIdToken: () => Promise.resolve('mock-token') },
  },
}))

describe('apiClient', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  it('apiGet builds correct URL and parses JSON', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ data: 1 }),
    })
    const result = await apiGet('/portfolio')
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/portfolio'),
      expect.objectContaining({ method: undefined })
    )
    expect(result).toEqual({ data: 1 })
  })

  it('apiPost sends JSON body', async () => {
    fetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ ok: true }) })
    await apiPost('/strategies', { name: 'Test', code: 'x' })
    expect(fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ name: 'Test', code: 'x' }),
      })
    )
  })

  it('apiDelete does not send body by default', async () => {
    fetch.mockResolvedValueOnce({ ok: true, headers: new Headers({ 'content-length': '0' }) })
    await apiDelete('/runs')
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/runs'),
      expect.objectContaining({ method: 'DELETE', body: undefined })
    )
  })
})
