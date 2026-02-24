// ConfirmDialog -- custom popup for confirming actions like delete strategy, clear, so on
export function ConfirmDialog({ open, title, message, confirmLabel = 'Confirm', cancelLabel = 'Cancel', onConfirm, onCancel }) {
  if (!open) return null
  return (
    <div className="confirm-overlay" onClick={(e) => e.target === e.currentTarget && onCancel?.()}>
      <div className="confirm-dialog" onClick={(e) => e.stopPropagation()}>
        {title && <div className="confirm-title">{title}</div>}
        <div className="confirm-message">{message}</div>
        <div className="confirm-actions">
          <button type="button" className="confirm-cancel" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button type="button" className="confirm-confirm" onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
