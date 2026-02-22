import { useRef, useCallback } from 'react'

export function ResizeHandle({ direction, onResize, className = '' }) {
  const startRef = useRef(null)

  const handleMouseDown = useCallback((e) => {
    e.preventDefault()
    startRef.current = { x: e.clientX, y: e.clientY }
    const handleMouseMove = (e2) => {
      if (!startRef.current) return
      const dx = e2.clientX - startRef.current.x
      const dy = e2.clientY - startRef.current.y
      startRef.current = { x: e2.clientX, y: e2.clientY }
      onResize(direction === 'vertical' ? dx : 0, direction === 'horizontal' ? dy : 0)
    }
    const handleMouseUp = () => {
      startRef.current = null
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    document.body.style.cursor = direction === 'vertical' ? 'col-resize' : 'row-resize'
    document.body.style.userSelect = 'none'
  }, [direction, onResize])

  return (
    <div
      className={`resize-handle resize-handle-${direction} ${className}`}
      onMouseDown={handleMouseDown}
    />
  )
}
