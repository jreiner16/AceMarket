// Watchlist -- select/search for stocks
import { useState, useEffect, useRef } from 'react'
import { apiGet } from './apiClient'

export function Watchlist({ items, selectedSymbol, onSelect, onAdd, onRemove }) {
  const [addInput, setAddInput] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchLoading, setSearchLoading] = useState(false)
  const [quotes, setQuotes] = useState({})
  const debounceRef = useRef(null)
  const searchContainerRef = useRef(null)
  const symbolsKey = (items || []).join(',')

  useEffect(() => {
    if (!symbolsKey) {
      const t = setTimeout(() => setQuotes({}), 0)
      return () => clearTimeout(t)
    }
    apiGet(`/watchlist/quotes?symbols=${encodeURIComponent(symbolsKey)}`)
      .then((data) => {
        const map = {}
        data.forEach((q) => { map[q.symbol] = q })
        setQuotes(map)
      })
      .catch(() => setQuotes({}))
  }, [symbolsKey])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (addInput.length < 2) {
      setSearchResults([])
      setSearchOpen(false)
      setSearchLoading(false)
      return
    }
    debounceRef.current = setTimeout(() => {
      setSearchLoading(true)
      apiGet(`/search?q=${encodeURIComponent(addInput)}`)
        .then((data) => {
          setSearchResults(Array.isArray(data) ? data : [])
          setSearchOpen(true)
        })
        .catch(() => setSearchResults([]))
        .finally(() => setSearchLoading(false))
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [addInput])

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target)) {
        setSearchOpen(false)
      }
    }
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [])

  const handleAdd = (e) => {
    e?.preventDefault()
    if (searchOpen && searchResults.length > 0) {
      handleSelectSearchResult(searchResults[0])
      return
    }
    const symbol = addInput.trim().toUpperCase()
    if (symbol && !items.includes(symbol)) {
      onAdd(symbol)
      setAddInput('')
      setSearchResults([])
      setSearchOpen(false)
    }
  }

  const handleSelectSearchResult = (item) => {
    if (item.symbol && !items.includes(item.symbol)) {
      onAdd(item.symbol)
    }
    setAddInput('')
    setSearchResults([])
    setSearchOpen(false)
  }

  const handleRemove = (e, symbol) => {
    e.stopPropagation()
    onRemove(symbol)
  }

  return (
    <div className="watchlist">
      <div className="watchlist-header">
        <span className="watchlist-title">Watchlist</span>
        <form onSubmit={handleAdd} className="watchlist-add-form watchlist-search-wrap" ref={searchContainerRef}>
          <span className="watchlist-search-icon">{searchLoading ? '…' : '⌕'}</span>
          <input
            type="text"
            className="watchlist-add-input"
            placeholder="Search tickers..."
            value={addInput}
            onChange={(e) => setAddInput(e.target.value)}
            onFocus={() => searchResults.length > 0 && setSearchOpen(true)}
          />
          {searchOpen && searchResults.length > 0 && (
            <div className="watchlist-search-results">
              {searchResults.map((r) => (
                <div
                  key={r.symbol}
                  className="watchlist-search-result-item"
                  onClick={() => handleSelectSearchResult(r)}
                >
                  <div className="watchlist-search-result-symbol">{r.symbol}</div>
                  <div className="watchlist-search-result-name">{r.name}</div>
                </div>
              ))}
            </div>
          )}
        </form>
      </div>
      {items.map((sym) => {
        const q = quotes[sym]
        const change = q?.change
        const changePct = q?.change_pct
        const hasChange = change != null && change !== 0
        return (
          <div
            key={sym}
            className={`watchlist-item ${selectedSymbol === sym ? 'active' : ''}`}
            onClick={() => onSelect(sym)}
          >
            <span className="watchlist-symbol">{sym}</span>
            <span className="watchlist-quote">
              {q?.price != null ? (
                <>
                  <span className="watchlist-price">${q.price.toFixed(2)}</span>
                  {hasChange && (
                    <span className={`watchlist-change ${change >= 0 ? 'positive' : 'negative'}`}>
                      {change >= 0 ? '+' : ''}{change.toFixed(2)} ({change >= 0 ? '+' : ''}{changePct.toFixed(2)}%)
                    </span>
                  )}
                </>
              ) : (
                <span className="watchlist-loading">…</span>
              )}
            </span>
            <button
              type="button"
              className="watchlist-remove"
              onClick={(e) => handleRemove(e, sym)}
              title="Remove from watchlist"
            >
              ×
            </button>
          </div>
        )
      })}
    </div>
  )
}
