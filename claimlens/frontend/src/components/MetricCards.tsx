import React from 'react'
import { Stats } from '../types'
import { Activity, CheckCircle2, CircleAlert, FileWarning, Gauge, Users } from 'lucide-react'

interface Props {
  stats: Stats | null
}

function Card({ label, value, sub, color, icon: Icon }: { label: string; value: string | number; sub?: string; color?: string; icon: React.ElementType }) {
  return (
    <div className="metric-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="metric-label">{label}</p>
          <p className={`text-2xl font-semibold mt-1.5 tabular-nums ${color || 'text-slate-900'}`}>{value}</p>
        </div>
        <span className="metric-icon"><Icon size={16} strokeWidth={1.8} /></span>
      </div>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </div>
  )
}

export function MetricCards({ stats }: Props) {
  if (!stats) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="bg-white rounded-xl border border-slate-200 p-4 h-20 animate-pulse">
            <div className="h-3 bg-slate-200 rounded w-3/4 mb-2" />
            <div className="h-6 bg-slate-200 rounded w-1/2" />
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      <Card
        icon={Users}
        label="Patients Synced"
        value={stats.total_patients}
        sub="across 3 facilities"
        color="text-slate-900"
      />
      <Card
        icon={CheckCircle2}
        label="Ready to Bill"
        value={stats.auto_accept}
        sub="auto_accept"
        color="text-green-600"
      />
      <Card
        icon={CircleAlert}
        label="Needs Review"
        value={stats.flag_for_review}
        sub="flag_for_review"
        color="text-amber-600"
      />
      <Card
        icon={FileWarning}
        label="Not Eligible"
        value={stats.reject}
        sub="reject"
        color="text-red-500"
      />
      <Card
        icon={Activity}
        label="API Retries"
        value={stats.api_health.total_retries}
        sub={`${stats.api_health.total_429s} rate limits hit`}
        color="text-sky-600"
      />
      <Card
        icon={Gauge}
        label="Avg Confidence"
        value={`${stats.avg_confidence_pct}%`}
        sub="extraction accuracy"
        color="text-violet-600"
      />
    </div>
  )
}
