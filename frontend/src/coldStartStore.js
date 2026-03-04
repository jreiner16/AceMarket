// coldStartStore -- show loading modal when API is slow (e.g. cold start)
const listeners = new Set()
let show = false
let pendingCount = 0
let showTimer = null
const DELAY_MS = 0

function emit() {
  listeners.forEach((fn) => fn(show))
}

export function subscribe(fn) {
  listeners.add(fn)
  fn(show)
  return () => listeners.delete(fn)
}

export function getShow() {
  return show
}

function setShow(value) {
  if (show !== value) {
    show = value
    emit()
  }
}

export function onRequestStart() {
  pendingCount++
  if (DELAY_MS === 0) {
    setShow(true)
  } else if (!showTimer) {
    showTimer = setTimeout(() => {
      showTimer = null
      setShow(true)
    }, DELAY_MS)
  }
}

export function onRequestEnd() {
  pendingCount--
  if (pendingCount <= 0) {
    pendingCount = 0
    if (showTimer) {
      clearTimeout(showTimer)
      showTimer = null
    }
    setShow(false)
  }
}
