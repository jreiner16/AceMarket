import { useState, useEffect, useCallback, useRef } from 'react'
import { uploadFile, downloadFileAsText } from './storageUtils'

const DEFAULT_WATCHLIST = ['AAPL', 'MSFT', 'GOOGL', 'TSLA']
const STORAGE_PATH = (uid) => `users/${uid}/data.json`
const LOCAL_KEY = (uid) => `acemarket_watchlist_${uid}`
const SAVE_DEBOUNCE_MS = 1500

function loadFromLocal(uid) {
  try {
    const raw = localStorage.getItem(LOCAL_KEY(uid))
    if (raw) {
      const data = JSON.parse(raw)
      if (Array.isArray(data.watchlist) && data.watchlist.length > 0) {
        return data.watchlist
      }
    }
  } catch {
    // ignore
  }
  return null
}

function saveToLocal(uid, data) {
  try {
    localStorage.setItem(LOCAL_KEY(uid), JSON.stringify(data))
  } catch {
    // ignore
  }
}

export function useUserData(user) {
  const [watchlist, setWatchlist] = useState(DEFAULT_WATCHLIST)
  const [loading, setLoading] = useState(true)
  const saveTimeoutRef = useRef(null)

  const load = useCallback(async (uid) => {
    try {
      const text = await downloadFileAsText(STORAGE_PATH(uid))
      const data = JSON.parse(text)
      if (Array.isArray(data.watchlist) && data.watchlist.length > 0) {
        setWatchlist(data.watchlist)
        saveToLocal(uid, { watchlist: data.watchlist })
        setLoading(false)
        return
      }
    } catch {
      // Firebase failed - try localStorage
    }
    const local = loadFromLocal(uid)
    if (local) {
      setWatchlist(local)
    }
    setLoading(false)
  }, [])

  const save = useCallback(async (uid, data) => {
    saveToLocal(uid, data)
    try {
      const blob = new Blob([JSON.stringify(data)], { type: 'application/json' })
      await uploadFile(STORAGE_PATH(uid), blob)
    } catch (err) {
      console.warn('Watchlist Firebase save failed, using local storage:', err?.message || err)
    }
  }, [])

  useEffect(() => {
    if (!user) {
      setWatchlist(DEFAULT_WATCHLIST)
      setLoading(false)
      return
    }
    setLoading(true)
    load(user.uid)
  }, [user?.uid, load])

  const setWatchlistAndSave = useCallback(
    (updater) => {
      setWatchlist((prev) => {
        const next = typeof updater === 'function' ? updater(prev) : updater
        if (user) {
          saveToLocal(user.uid, { watchlist: next })
          if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
          saveTimeoutRef.current = setTimeout(() => {
            save(user.uid, { watchlist: next }).catch(() => {})
            saveTimeoutRef.current = null
          }, SAVE_DEBOUNCE_MS)
        }
        return next
      })
    },
    [user, save]
  )

  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
    }
  }, [])

  return {
    watchlist,
    setWatchlist: setWatchlistAndSave,
    loading,
  }
}
