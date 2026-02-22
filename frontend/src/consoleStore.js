/**
 * Global console log store. Intercepts console.log/warn/error and stores entries.
 */
const listeners = new Set()
let entries = []
const MAX_ENTRIES = 500

function emit() {
  listeners.forEach((fn) => fn([...entries]))
}

function addEntry(level, args) {
  const message = args.map((a) => {
    if (a instanceof Error) return a.stack || a.message
    if (typeof a === 'object') try { return JSON.stringify(a) } catch { return String(a) }
    return String(a)
  }).join(' ')
  entries.push({
    ts: new Date().toISOString(),
    level,
    message,
  })
  if (entries.length > MAX_ENTRIES) entries = entries.slice(-MAX_ENTRIES)
  emit()
}

export function subscribe(fn) {
  listeners.add(fn)
  fn([...entries])
  return () => listeners.delete(fn)
}

export function clear() {
  entries = []
  emit()
}

export function clearErrors() {
  entries = entries.filter((e) => e.level !== 'error')
  emit()
}

export function install() {
  if (window.__ACE_CONSOLE_STORE_INSTALLED__) return
  window.__ACE_CONSOLE_STORE_INSTALLED__ = true

  const origLog = console.log
  const origWarn = console.warn
  const origError = console.error

  console.log = (...args) => {
    addEntry('log', args)
    origLog.apply(console, args)
  }
  console.warn = (...args) => {
    addEntry('warn', args)
    origWarn.apply(console, args)
  }
  console.error = (...args) => {
    addEntry('error', args)
    origError.apply(console, args)
  }

  window.addEventListener('error', (e) => {
    addEntry('error', [`${e.message} at ${e.filename}:${e.lineno}`])
  })

  window.addEventListener('unhandledrejection', (e) => {
    addEntry('error', [e.reason instanceof Error ? e.reason.message : String(e.reason)])
  })

  const origFetch = window.fetch
  window.fetch = async (...args) => {
    try {
      const res = await origFetch(...args)
      if (!res.ok) {
        const url = typeof args[0] === 'string' ? args[0] : args[0]?.url
        let body = ''
        try { body = await res.clone().text() } catch (e) { void e }
        addEntry('error', [`${res.status} ${res.statusText}: ${url}${body ? ` - ${body.slice(0, 200)}` : ''}`])
      }
      return res
    } catch (e) {
      if (e?.name === 'AbortError') throw e
      addEntry('error', [`Fetch failed: ${e.message}`])
      throw e
    }
  }
}
