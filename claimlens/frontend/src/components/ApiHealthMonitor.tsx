import React from 'react'
import { ApiHealth } from '../types'

interface Props {
  health: ApiHealth | null
  lastSync: string | null
}

function Stat({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="text-center">
      <p className={`text-lg font-bold ${color || 'text-slate-700'}`}>{value}</p>
      <p className="text-xs text-slate-400">{label}</p>
    </div>
  )
}

export function ApiHealthMonitor({ health, lastSync }: Props) {
  if (!health) return null

  const hitRate = health.total_requests > 0
    ? Math.round((health.total_429s / health.total_requests) * 100)
    : 0

  const successRate = health.total_requests > 0
    ? Math.round(((health.total_requests - health.failed_requests) / health.total_requests) * 100)
    : 100

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
          <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">API Pipeline Health</span>
        </div>
        {lastSync && (
          <span className="text-xs text-slate-400">
            Last sync: {new Date(lastSync).toLocaleString()}
          </span>
        )}
      </div>
      <div className="grid grid-cols-5 gap-4 divide-x divide-slate-100">
        <Stat label="Total Requests" value={health.total_requests.toLocaleString()} />
        <Stat label="429s Handled" value={health.total_429s.toLocaleString()} color="text-amber-600" />
        <Stat label="Hit Rate" value={`${hitRate}%`} color={hitRate > 35 ? 'text-red-500' : 'text-amber-500'} />
        <Stat label="Avg Retry Delay" value={`${health.avg_retry_delay_s}s`} color="text-sky-600" />
        <Stat label="Success Rate" value={`${successRate}%`} color="text-green-600" />
      </div>
      <div className="mt-3 flex items-center gap-2">
        <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-green-500 to-sky-500 rounded-full"
            style={{ width: `${successRate}%` }}
          />
        </div>
        <span className="text-xs text-slate-500">
          {health.failed_requests === 0
            ? 'All requests succeeded after retry'
            : `${health.failed_requests} failed after max retries`}
        </span>
      </div>
    </div>
  )
}
