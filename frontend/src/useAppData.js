// useAppData -- parallel fetch: light bootstrap (runs+watchlist) + portfolio. Fast time-to-content.
import { useState, useEffect, useCallback, useRef } from 'react'
import { apiGet, apiPut } from './apiClient'

const DEFAULT_WATCHLIST = ['AAPL', 'MSFT', 'GOOGL', 'TSLA']
const SAVE_DEBOUNCE_MS = 500
const LOCAL_KEY = (uid) => `acemarket_watchlist_${uid}`

function loadFromLocal(uid) {
  try {
    const raw = localStorage.getItem(LOCAL_KEY(uid))
    if (raw) {
      const data = JSON.parse(raw)
      if (Array.isArray(data.watchlist) && data.watchlist.length > 0) return data.watchlist
    }
  } catch {
    /* ignore */
  }
  return null
}

function saveToLocal(uid, wl) {
  try {
    localStorage.setItem(LOCAL_KEY(uid), JSON.stringify({ watchlist: wl }))
  } catch {
    /* ignore */
  }
}

export function useAppData(user) {
  const [portfolio, setPortfolio] = useState(null)
  const [runs, setRuns] = useState([])
  const [watchlist, setWatchlistState] = useState(DEFAULT_WATCHLIST)
  const [loading, setLoading] = useState(true)
  const saveTimeoutRef = useRef(null)
  const pendingRef = useRef(null)

  const fetchBootstrap = useCallback(() => {
    if (!user) return
    setLoading(true)
    // Fetch light bootstrap (fast) and portfolio (slower) in parallel
    const bootstrapPromise = apiGet('/bootstrap')
    const portfolioPromise = apiGet('/portfolio')
    Promise.all([bootstrapPromise, portfolioPromise])
      .then(([bootstrap, port]) => {
        setRuns(bootstrap?.runs ?? [])
        const wl = bootstrap?.watchlist
        if (Array.isArray(wl) && wl.length > 0) {
          setWatchlistState(wl)
          saveToLocal(user.uid, wl)
        }
        if (port) setPortfolio(port)
      })
      .catch(() => {
        setPortfolio(null)
        setRuns([])
        const local = loadFromLocal(user?.uid)
        if (local?.length) setWatchlistState(local)
      })
      .finally(() => setLoading(false))
  }, [user])

  useEffect(() => {
    if (!user) {
      queueMicrotask(() => {
        setPortfolio(null)
        setRuns([])
        setWatchlistState(DEFAULT_WATCHLIST)
        setLoading(false)
      })
      return
    }
    queueMicrotask(() => fetchBootstrap())
  }, [user?.uid, fetchBootstrap, user])

  const refresh = useCallback(() => {
    fetchBootstrap()
  }, [fetchBootstrap])

  const saveWatchlist = useCallback((wl) => {
    if (!user) return
    apiPut('/watchlist', { watchlist: wl }).catch(() => {})
  }, [user])

  const setWatchlist = useCallback(
    (updater) => {
      setWatchlistState((prev) => {
        const next = typeof updater === 'function' ? updater(prev) : updater
        if (user) {
          saveToLocal(user.uid, next)
          pendingRef.current = next
          if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
          saveTimeoutRef.current = setTimeout(() => {
            if (pendingRef.current) {
              saveWatchlist(pendingRef.current)
              pendingRef.current = null
            }
            saveTimeoutRef.current = null
          }, SAVE_DEBOUNCE_MS)
        }
        return next
      })
    },
    [user, saveWatchlist]
  )

  const flushPending = useCallback(() => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current)
      saveTimeoutRef.current = null
    }
    if (pendingRef.current && user) {
      saveWatchlist(pendingRef.current)
      pendingRef.current = null
    }
  }, [user, saveWatchlist])

  useEffect(() => {
    const onBeforeUnload = () => flushPending()
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => {
      window.removeEventListener('beforeunload', onBeforeUnload)
      flushPending()
    }
  }, [flushPending])

  return {
    portfolio,
    runs,
    watchlist,
    setWatchlist,
    loading,
    refresh,
    fetchRuns: fetchBootstrap,
  }
}
