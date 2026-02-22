import { useState, useEffect } from 'react'
import { subscribe, clear, clearErrors } from './consoleStore'

export function ConsolePanel() {
  const [entries, setEntries] = useState([])

  useEffect(() => subscribe(setEntries), [])

  const errorCount = entries.filter((e) => e.level === 'error').length

  return (
    <div className="console-panel report-panel report-legacy">
      <div className="report-header report-legacy-header">
        <span className="report-title">Console</span>
        <div className="console-header-actions">
          {errorCount > 0 && (
            <button type="button" className="console-clear-errors" onClick={clearErrors}>
              Clear errors
            </button>
          )}
          <button type="button" className="console-clear" onClick={clear}>
            Clear
          </button>
        </div>
      </div>
      <div className="console-output report-content report-legacy-content">
        {entries.length === 0 ? (
          <div className="console-empty">No messages</div>
        ) : (
          entries.map((e, i) => (
            <div key={i} className={`console-entry console-${e.level}`}>
              <span className="console-time">{e.ts.slice(11, 23)}</span>
              <span className="console-level">[{e.level}]</span>
              <span className="console-msg">{e.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
