// UseUserData -- sync watchlist with backend (persisted per user)
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
    // localStorage may be unavailable (private mode, etc.)
  }
  return null
}

function saveToLocal(uid, wl) {
  try {
    localStorage.setItem(LOCAL_KEY(uid), JSON.stringify({ watchlist: wl }))
  } catch {
    // localStorage may be full or unavailable
  }
}

export function useUserData(user) {
  const [watchlist, setWatchlist] = useState(DEFAULT_WATCHLIST)
  const [loading, setLoading] = useState(true)
  const saveTimeoutRef = useRef(null)
  const pendingRef = useRef(null)

  useEffect(() => {
    if (!user) {
      queueMicrotask(() => {
        setWatchlist(DEFAULT_WATCHLIST)
        setLoading(false)
      })
      return
    }
    // Sync loading state when starting fetch (legitimate effect pattern)
    setLoading(true) // eslint-disable-line react-hooks/set-state-in-effect
    const uid = user.uid
    const local = loadFromLocal(uid)
    apiGet('/watchlist')
      .then((data) => {
        const wl = data?.watchlist
        if (Array.isArray(wl) && wl.length > 0) {
          saveToLocal(uid, wl)
          return wl
        }
        return null
      })
      .catch(() => null)
      .then((fromApi) => {
        if (fromApi && fromApi.length > 0) {
          setWatchlist(fromApi)
        } else if (local && local.length > 0) {
          setWatchlist(local)
        }
        setLoading(false)
      })
  }, [user?.uid]) // eslint-disable-line react-hooks/exhaustive-deps -- user.uid is the intended trigger

  const saveWatchlist = useCallback((wl) => {
    if (!user) return
    apiPut('/watchlist', { watchlist: wl }).catch(() => { })
  }, [user])

  const setWatchlistAndSave = useCallback(
    (updater) => {
      setWatchlist((prev) => {
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
    watchlist,
    setWatchlist: setWatchlistAndSave,
    loading,
  }
}
