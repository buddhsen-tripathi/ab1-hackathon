import React from 'react'
import { Patient } from '../types'
import { DecisionBadge } from './DecisionBadge'
import { ScoreRing } from './ScoreRing'

interface Props {
  patients: Patient[]
  onSelect: (p: Patient) => void
  loading?: boolean
}

export function PatientTable({ patients, onSelect, loading }: Props) {
  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-14 bg-white rounded-lg border border-slate-200 animate-pulse" />
        ))}
      </div>
    )
  }

  if (patients.length === 0) {
    return (
      <div className="text-center py-16 text-slate-400">
        <p className="text-4xl mb-3">📋</p>
        <p className="text-sm font-medium">No patients found</p>
        <p className="text-xs mt-1">Run a sync to load patient data</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 border-b border-slate-200 sticky top-0 z-10">
          <tr>
            <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Patient</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Facility</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Primary Wound</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Coverage</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Score</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Decision</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Missing</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {patients.map(p => {
            const name = [p.first_name, p.last_name].filter(Boolean).join(' ') || p.patient_id
            const woundDesc = [
              p.wound_stage ? `Stage ${p.wound_stage}` : null,
              p.wound_type,
            ].filter(Boolean).join(' ')
            const missing = p.missing_fields || []

            return (
              <tr
                key={p.patient_id}
                className="hover:bg-sky-50 cursor-pointer transition-colors group"
                onClick={() => onSelect(p)}
              >
                <td className="px-4 py-3">
                  <div>
                    <p className="font-semibold text-slate-900 group-hover:text-sky-700 transition-colors">{name}</p>
                    <p className="text-xs text-slate-400 font-mono">{p.patient_id}</p>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className="text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded font-medium">{p.facility_name}</span>
                </td>
                <td className="px-4 py-3">
                  {woundDesc ? (
                    <div>
                      <p className="text-slate-800 font-medium">{woundDesc}</p>
                      {p.wound_location && (
                        <p className="text-xs text-slate-400">{p.wound_location}</p>
                      )}
                    </div>
                  ) : (
                    <span className="text-slate-300 text-xs italic">No wound documented</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {p.has_medicare_part_b ? (
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-sky-700 bg-sky-50 border border-sky-200 px-2 py-1 rounded-full">
                      <span className="w-1.5 h-1.5 bg-sky-500 rounded-full" />
                      MCB
                    </span>
                  ) : (
                    <span className="text-xs text-slate-400">{p.primary_payer_code || '—'}</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <ScoreRing score={p.claim_score} size={44} />
                </td>
                <td className="px-4 py-3">
                  <DecisionBadge decision={p.routing_decision} />
                </td>
                <td className="px-4 py-3">
                  {missing.length > 0 ? (
                    <div className="flex flex-wrap gap-1 max-w-48">
                      {missing.slice(0, 2).map(m => (
                        <span key={m} className="text-xs bg-red-50 text-red-600 border border-red-100 px-1.5 py-0.5 rounded">
                          {m}
                        </span>
                      ))}
                      {missing.length > 2 && (
                        <span className="text-xs text-slate-400">+{missing.length - 2} more</span>
                      )}
                    </div>
                  ) : (
                    <span className="text-green-500 text-xs font-medium">Complete</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <button
                    className="text-xs font-medium text-sky-600 hover:text-sky-800 hover:underline"
                    onClick={e => { e.stopPropagation(); onSelect(p) }}
                  >
                    View packet →
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
