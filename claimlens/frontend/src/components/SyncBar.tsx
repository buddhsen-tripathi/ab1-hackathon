import React from 'react'
import { SyncStatus } from '../types'

interface Props {
  status: SyncStatus | null
  onSync: () => void
}

export function SyncBar({ status, onSync }: Props) {
  const running = status?.running
  const pct = status && status.total > 0
    ? Math.round((status.processed / status.total) * 100)
    : 0

  return (
    <div className="flex items-center gap-3">
      {running && (
        <div className="flex-1 max-w-xs">
          <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
            <span className="truncate">{status?.current_step}</span>
            <span className="flex-shrink-0 ml-2">{status?.processed}/{status?.total}</span>
          </div>
          <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-sky-500 rounded-full transition-all duration-300"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      )}
      {status?.status === 'complete' && !running && (
        <span className="text-xs text-green-600 font-medium">✓ Sync complete</span>
      )}
      <button
        onClick={onSync}
        disabled={!!running}
        className={`flex items-center gap-2 text-sm font-semibold px-4 py-2 rounded-lg transition-all ${
          running
            ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
            : 'bg-sky-600 hover:bg-sky-700 text-white shadow-sm syncing'
        }`}
      >
        {running ? (
          <>
            <span className="inline-block w-3.5 h-3.5 border-2 border-slate-300 border-t-slate-500 rounded-full animate-spin" />
            Syncing...
          </>
        ) : (
          <>
            <span>↻</span>
            Sync Data
          </>
        )}
      </button>
    </div>
  )
}
