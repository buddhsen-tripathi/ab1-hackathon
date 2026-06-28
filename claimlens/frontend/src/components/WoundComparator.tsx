import React from 'react'
import { Patient } from '../types'
import { Check } from 'lucide-react'

interface Props {
  patient: Patient
}

function completeness(w: any): number {
  const fields = ['wound_type', 'wound_location', 'wound_stage', 'length_cm', 'width_cm', 'depth_cm', 'drainage']
  const found = fields.filter(f => w[f] !== null && w[f] !== undefined).length
  return Math.round((found / fields.length) * 100)
}

function volume(w: any): string {
  const l = w.length_cm || 0
  const wd = w.width_cm || 0
  const d = w.depth_cm || 0.1
  const vol = l * wd * d
  return vol > 0 ? `${vol.toFixed(1)} cm³` : '—'
}

export function WoundComparator({ patient }: Props) {
  const wounds = patient.all_wounds
  if (!Array.isArray(wounds) || wounds.length === 0) return null

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Multi-Wound Note Detected</span>
        <span className="bg-violet-100 text-violet-700 text-xs px-2 py-0.5 rounded-full font-medium">{wounds.length} wounds</span>
      </div>
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="text-left px-3 py-2 text-xs font-semibold text-slate-500">#</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-slate-500">Wound Type</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-slate-500">Location</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-slate-500">Size</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-slate-500">Stage</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-slate-500">Complete</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-slate-500">Selected</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {wounds.map((w: any, idx: number) => {
              const pct = completeness(w)
              const isPrimary = idx === 0
              return (
                <tr key={idx} className={isPrimary ? 'bg-green-50' : 'bg-white'}>
                  <td className="px-3 py-2 text-slate-500 font-mono text-xs">{idx + 1}</td>
                  <td className="px-3 py-2 font-medium text-slate-800">{w.wound_type || '—'}</td>
                  <td className="px-3 py-2 text-slate-600">{w.wound_location || '—'}</td>
                  <td className="px-3 py-2 text-slate-600 font-mono text-xs">{volume(w)}</td>
                  <td className="px-3 py-2 text-slate-600">{w.wound_stage ? `Stage ${w.wound_stage}` : '—'}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 bg-slate-200 rounded-full h-1.5 min-w-12">
                        <div
                          className="bg-sky-500 h-1.5 rounded-full"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-xs text-slate-500 w-8">{pct}%</span>
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    {isPrimary ? (
                      <span className="text-green-600" title="Primary wound selected"><Check size={17} /></span>
                    ) : (
                      <span className="text-slate-300">—</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-400 mt-2">
        Primary wound selected by completeness × severity × volume scoring.
      </p>
    </div>
  )
}
