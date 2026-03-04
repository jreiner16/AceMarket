// coldStartStore -- simple loading indicator when API is slow
const listeners = new Set()
let show = false
let pendingCount = 0
let showTimer = null
let suppress = false
const DELAY_MS = 3000

function emit() {
  listeners.forEach((fn) => fn(show))
}

function setShow(value) {
  if (show !== value) {
    show = value
    emit()
  }
}

export function subscribe(fn) {
  listeners.add(fn)
  fn(show)
  return () => listeners.delete(fn)
}

export function getShow() {
  return show
}

export function setSuppress(value) {
  suppress = value
  if (suppress && show) {
    show = false
    emit()
  }
}

export function onRequestStart(skipLoading = false) {
  pendingCount++
  if (skipLoading || suppress) return
  if (!showTimer) {
    showTimer = setTimeout(() => {
      showTimer = null
      if (!suppress) setShow(true)
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
    if (!suppress) setShow(false)
  }
}
