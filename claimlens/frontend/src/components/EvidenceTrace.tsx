import React from 'react'
import { Patient } from '../types'

interface Props {
  patient: Patient
}

const FIELD_LABELS: Record<string, string> = {
  wound_type: 'Wound Type',
  location: 'Location',
  stage: 'Stage',
  length: 'Length',
  width: 'Width',
  depth: 'Depth',
  drainage: 'Drainage',
  coverage: 'Coverage',
}

function sourceLabel(source: string | null): string {
  if (!source) return 'Unknown'
  if (source === 'assessment') return 'Assessment'
  if (source === 'note_structured_spn') return 'Structured Note'
  if (source === 'note_prose') return 'Progress Note'
  if (source === 'note_llm') return 'Note (AI)'
  return source
}

function fieldValue(patient: Patient, field: string): string | null {
  const map: Record<string, string | number | null> = {
    wound_type: patient.wound_type,
    location: patient.wound_location,
    stage: patient.wound_stage ? `Stage ${patient.wound_stage}` : null,
    length: patient.length_cm ? `${patient.length_cm} cm` : null,
    width: patient.width_cm ? `${patient.width_cm} cm` : null,
    depth: patient.depth_cm ? `${patient.depth_cm} cm` : null,
    drainage: patient.drainage ? patient.drainage.charAt(0).toUpperCase() + patient.drainage.slice(1) : null,
    coverage: patient.has_medicare_part_b ? 'Medicare Part B (Active)' : null,
  }
  return map[field] as string | null
}

export function EvidenceTrace({ patient }: Props) {
  const evidence = patient.evidence_trace || {}
  const src = patient.extraction_source

  const rows = [
    ...Object.keys(FIELD_LABELS),
    ...(patient.has_medicare_part_b ? ['coverage'] : []),
  ]

  const dataRows = rows.filter(f => fieldValue(patient, f) || evidence[f])

  if (dataRows.length === 0) {
    return (
      <p className="text-sm text-slate-400 italic py-4">No evidence extracted for this patient.</p>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-100">
            <th className="text-left py-2 pr-4 text-xs font-semibold text-slate-500 uppercase tracking-wide w-24">Field</th>
            <th className="text-left py-2 pr-4 text-xs font-semibold text-slate-500 uppercase tracking-wide w-32">Value</th>
            <th className="text-left py-2 pr-4 text-xs font-semibold text-slate-500 uppercase tracking-wide w-24">Source</th>
            <th className="text-left py-2 text-xs font-semibold text-slate-500 uppercase tracking-wide">Evidence</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-50">
          {dataRows.map(field => {
            const val = fieldValue(patient, field)
            const quote = evidence[field]
            const hasValue = !!val
            return (
              <tr key={field} className="hover:bg-slate-50 transition-colors">
                <td className="py-2 pr-4 font-medium text-slate-700 whitespace-nowrap">
                  {FIELD_LABELS[field] || field}
                </td>
                <td className="py-2 pr-4">
                  {val ? (
                    <span className="text-slate-900 font-medium">{val}</span>
                  ) : (
                    <span className="text-red-400 text-xs">Not found</span>
                  )}
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">
                  {field === 'coverage' ? (
                    <span className="text-xs bg-sky-50 text-sky-700 border border-sky-200 px-2 py-0.5 rounded-full">Coverage API</span>
                  ) : hasValue ? (
                    <span className="text-xs bg-violet-50 text-violet-700 border border-violet-200 px-2 py-0.5 rounded-full">
                      {sourceLabel(src)}
                    </span>
                  ) : (
                    <span className="text-xs text-slate-300">—</span>
                  )}
                </td>
                <td className="py-2">
                  {quote ? (
                    <span className="text-slate-500 text-xs font-mono bg-slate-50 px-2 py-0.5 rounded border border-slate-100 line-clamp-1">
                      {quote}
                    </span>
                  ) : field === 'coverage' && patient.has_medicare_part_b ? (
                    <span className="text-slate-500 text-xs">"active coverage record found"</span>
                  ) : (
                    <span className="text-slate-300 text-xs">—</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
