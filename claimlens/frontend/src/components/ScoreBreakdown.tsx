import React from 'react'
import { Patient } from '../types'

interface Props {
  patient: Patient
}

export function ScoreBreakdown({ patient }: Props) {
  const bd = patient.score_breakdown
  if (!bd) return null

  const items = Object.entries(bd)

  return (
    <div className="space-y-1.5">
      {items.map(([key, item]) => {
        if (item.earned === null) return null
        const isNeg = item.points < 0
        return (
          <div key={key} className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <span className={`flex-shrink-0 w-4 h-4 rounded-full flex items-center justify-center text-xs font-bold ${
                item.earned
                  ? isNeg
                    ? 'bg-red-100 text-red-600'
                    : 'bg-green-100 text-green-600'
                  : 'bg-slate-100 text-slate-400'
              }`}>
                {item.earned ? (isNeg ? '−' : '✓') : '○'}
              </span>
              <span className={`truncate ${item.earned ? 'text-slate-700' : 'text-slate-400'}`}>
                {item.label}
              </span>
            </div>
            <span className={`flex-shrink-0 font-mono text-xs font-semibold ml-2 ${
              item.earned
                ? isNeg ? 'text-red-500' : 'text-green-600'
                : 'text-slate-300'
            }`}>
              {item.points > 0 ? `+${item.points}` : item.points}
            </span>
          </div>
        )
      })}
      <div className="border-t border-slate-200 pt-2 mt-2 flex items-center justify-between">
        <span className="text-sm font-semibold text-slate-700">Total Score</span>
        <span className="font-bold text-slate-900">{patient.claim_score}/100</span>
      </div>
    </div>
  )
}
