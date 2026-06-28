import React, { useEffect, useState } from 'react'
import { Patient } from '../types'
import { ScoreRing } from './ScoreRing'
import { DecisionBadge } from './DecisionBadge'
import { EvidenceTrace } from './EvidenceTrace'
import { WoundComparator } from './WoundComparator'
import { ScoreBreakdown } from './ScoreBreakdown'
import { Bot, Check, CheckCircle2, Copy, RefreshCw, Sparkles, X, XCircle } from 'lucide-react'

interface Props {
  patient: Patient | null
  onClose: () => void
}

type Tab = 'packet' | 'evidence' | 'breakdown' | 'missing'

function TabBtn({ id, label, active, onClick, badge }: { id: Tab; label: string; active: boolean; onClick: () => void; badge?: number }) {
  return (
    <button
      onClick={onClick}
      className={`px-2 sm:px-3 py-2 text-xs sm:text-sm font-medium border-b-2 transition-colors whitespace-nowrap flex items-center gap-1.5 ${
        active
          ? 'border-sky-500 text-sky-600'
          : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
      }`}
    >
      {label}
      {badge !== undefined && badge > 0 && (
        <span className="bg-red-100 text-red-600 text-xs font-semibold px-1.5 py-0.5 rounded-full">{badge}</span>
      )}
    </button>
  )
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      }}
      className="inline-flex items-center gap-1.5 text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded-md transition-colors font-medium"
    >
      {copied ? <><Check size={13} /> Copied</> : <><Copy size={13} /> Copy</>}
    </button>
  )
}

export function PatientDrawer({ patient, onClose }: Props) {
  const [tab, setTab] = useState<Tab>('packet')
  const [summary, setSummary] = useState(patient?.summary_narrative || '')
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [summaryError, setSummaryError] = useState('')

  useEffect(() => {
    setTab('packet')
    setSummary(patient?.summary_narrative || '')
    setSummaryError('')
  }, [patient?.patient_id])

  if (!patient) return null

  const name = [patient.first_name, patient.last_name].filter(Boolean).join(' ') || patient.patient_id
  const missing = patient.missing_fields || []
  const isAccept = patient.routing_decision === 'auto_accept'
  const isReview = patient.routing_decision === 'flag_for_review'
  const isReject = patient.routing_decision === 'reject'

  const actionBg = isAccept
    ? 'bg-green-50 border-green-200'
    : isReview
      ? 'bg-amber-50 border-amber-200'
      : 'bg-red-50 border-red-200'
  const actionText = isAccept ? 'text-green-800' : isReview ? 'text-amber-800' : 'text-red-800'

  const woundDesc = [
    patient.wound_stage ? `Stage ${patient.wound_stage}` : null,
    patient.wound_type,
    patient.wound_location ? `· ${patient.wound_location}` : null,
  ].filter(Boolean).join(' ')

  const requestSummary = async () => {
    if (!patient) return
    setSummaryLoading(true)
    setSummaryError('')
    try {
      const response = await fetch(`/api/patients/${patient.patient_id}/ai-summary`, { method: 'POST' })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'Summary generation failed')
      setSummary(data.summary)
    } catch (error) {
      setSummaryError(error instanceof Error ? error.message : 'Summary generation failed')
    } finally {
      setSummaryLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end" onClick={onClose}>
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" />

      {/* Drawer */}
      <div
        className="relative w-full max-w-2xl bg-white shadow-2xl drawer-enter flex flex-col overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-slate-200 bg-white flex-shrink-0">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-mono text-slate-400">{patient.patient_id}</span>
              <span className="text-slate-300">·</span>
              <span className="text-sm text-slate-500">{patient.facility_name}</span>
              {!!patient.is_new_admission && (
                <span className="bg-sky-100 text-sky-700 text-xs px-2 py-0.5 rounded-full font-medium">New Admission</span>
              )}
            </div>
            <h2 className="text-xl font-bold text-slate-900">{name}</h2>
            {woundDesc && (
              <p className="text-sm text-slate-500 mt-0.5">{woundDesc}</p>
            )}
          </div>
          <div className="flex items-center gap-3">
            <ScoreRing score={patient.claim_score} size={72} />
            <button
              onClick={onClose}
              aria-label="Close claim packet"
              className="text-slate-400 hover:text-slate-600 text-xl font-light ml-2 w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100 transition-colors"
            >
              <X size={19} />
            </button>
          </div>
        </div>

        {/* Decision badge */}
        <div className="px-5 pt-3 pb-0 flex-shrink-0">
          <DecisionBadge decision={patient.routing_decision} score={patient.claim_score} showScore size="lg" />
        </div>

        {/* Tabs */}
        <div className="border-b border-slate-200 px-3 sm:px-5 flex gap-1 flex-shrink-0 overflow-x-auto">
          <TabBtn id="packet" label="Claim Packet" active={tab === 'packet'} onClick={() => setTab('packet')} />
          <TabBtn id="evidence" label="Evidence Trace" active={tab === 'evidence'} onClick={() => setTab('evidence')} />
          <TabBtn id="breakdown" label="Score Breakdown" active={tab === 'breakdown'} onClick={() => setTab('breakdown')} />
          {missing.length > 0 && (
            <TabBtn id="missing" label="Missing Docs" active={tab === 'missing'} onClick={() => setTab('missing')} badge={missing.length} />
          )}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5">

          {tab === 'packet' && (
            <div className="space-y-5">
              <section className="ai-summary-panel">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className="ai-summary-icon"><Bot size={16} /></span>
                    <div>
                      <h3 className="text-sm font-semibold text-slate-900">Claude packet summary</h3>
                      <p className="text-xs text-slate-500">Concise narrative for biller handoff</p>
                    </div>
                  </div>
                  <button className="secondary-button" onClick={requestSummary} disabled={summaryLoading}>
                    {summaryLoading ? <RefreshCw size={14} className="animate-spin" /> : <Sparkles size={14} />}
                    {summary ? 'Refresh' : 'Generate'}
                  </button>
                </div>
                {summary && <p className="mt-3 text-sm leading-6 text-slate-700">{summary}</p>}
                {!summary && !summaryError && <p className="mt-3 text-xs text-slate-500">Generate an evidence-constrained summary from this scored claim packet.</p>}
                {summaryError && <p className="mt-3 text-xs text-amber-700">{summaryError}</p>}
              </section>

              {/* Coverage */}
              <Section title="Coverage">
                <div className="flex items-center gap-2">
                  {patient.has_medicare_part_b ? (
                    <>
                      <CheckCircle2 className="text-emerald-600 flex-shrink-0" size={18} />
                      <span className="text-sm text-slate-700">
                        <strong>Active Medicare Part B</strong> — {patient.coverage_payer_name || 'Medicare Part B'}
                        {patient.coverage_effective_from && (
                          <span className="text-slate-400"> (since {patient.coverage_effective_from.slice(0,10)})</span>
                        )}
                      </span>
                    </>
                  ) : (
                    <>
                      <XCircle className="text-red-500 flex-shrink-0" size={18} />
                      <span className="text-sm text-slate-700">No active Medicare Part B coverage found</span>
                    </>
                  )}
                </div>
              </Section>

              {/* Wound Evidence */}
              <Section title="Wound Evidence">
                <div className="space-y-2">
                  {[
                    { label: 'Wound Type', value: patient.wound_type },
                    { label: 'Location', value: patient.wound_location },
                    { label: 'Stage', value: patient.wound_stage ? `Stage ${patient.wound_stage}` : null, onlyFor: 'pressure_ulcer' },
                    { label: 'Length', value: patient.length_cm ? `${patient.length_cm} cm` : null },
                    { label: 'Width', value: patient.width_cm ? `${patient.width_cm} cm` : null },
                    { label: 'Depth', value: patient.depth_cm ? `${patient.depth_cm} cm` : null },
                    { label: 'Drainage', value: patient.drainage },
                  ]
                    .filter(f => !(f.onlyFor && patient.wound_type !== f.onlyFor && !patient.wound_type?.toLowerCase().includes('pressure')))
                    .map(f => (
                      <div key={f.label} className="flex items-center gap-2 text-sm">
                        {f.value ? (
                          <CheckCircle2 className="text-emerald-600 flex-shrink-0" size={16} />
                        ) : (
                          <XCircle className="text-red-400 flex-shrink-0" size={16} />
                        )}
                        <span className="text-slate-500 w-20 flex-shrink-0">{f.label}:</span>
                        <span className={f.value ? 'text-slate-800 font-medium' : 'text-slate-400 italic'}>
                          {f.value || 'Not documented'}
                        </span>
                      </div>
                    ))}
                </div>
              </Section>

              {/* Biller Action */}
              <Section title="Biller Action">
                <div className={`rounded-lg border p-4 ${actionBg}`}>
                  <p className={`text-sm font-semibold ${actionText}`}>{patient.biller_action}</p>
                </div>
              </Section>

              {/* Routing Reason */}
              <Section title="Why">
                <p className="text-sm text-slate-600 leading-relaxed">{patient.routing_reason}</p>
              </Section>

              {/* Missing items */}
              {missing.length > 0 && (
                <Section title="What's Missing">
                  <div className="flex flex-wrap gap-2">
                    {missing.map(m => (
                      <span key={m} className="bg-red-50 border border-red-200 text-red-700 text-xs px-2.5 py-1 rounded-full font-medium">
                        {m}
                      </span>
                    ))}
                  </div>
                </Section>
              )}

              {/* Multi-wound */}
              {patient.is_multi_wound && (
                <Section title="Primary Wound Selector">
                  <WoundComparator patient={patient} />
                </Section>
              )}

              {/* Extraction metadata */}
              <Section title="Extraction Metadata">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-slate-400 text-xs">Source</p>
                    <p className="text-slate-700 font-medium capitalize">{patient.extraction_source?.replace('_', ' ') || '—'}</p>
                  </div>
                  <div>
                    <p className="text-slate-400 text-xs">Note Format</p>
                    <p className="text-slate-700 font-medium capitalize">{patient.note_format?.replace('_', ' ') || '—'}</p>
                  </div>
                  <div>
                    <p className="text-slate-400 text-xs">Confidence</p>
                    <p className="text-slate-700 font-medium">{Math.round((patient.extraction_confidence || 0) * 100)}%</p>
                  </div>
                  <div>
                    <p className="text-slate-400 text-xs">Multi-wound</p>
                    <p className="text-slate-700 font-medium">{patient.is_multi_wound ? 'Yes' : 'No'}</p>
                  </div>
                </div>
              </Section>
            </div>
          )}

          {tab === 'evidence' && (
            <div>
              <p className="text-xs text-slate-400 mb-4">
                Every field below links to the source record it was extracted from. No black-box routing.
              </p>
              <EvidenceTrace patient={patient} />
            </div>
          )}

          {tab === 'breakdown' && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-slate-700">Claim Readiness Score</h3>
                <div className="flex items-center gap-2">
                  <ScoreRing score={patient.claim_score} size={56} />
                  <DecisionBadge decision={patient.routing_decision} />
                </div>
              </div>
              <ScoreBreakdown patient={patient} />
              <div className="mt-4 p-3 bg-slate-50 rounded-lg text-xs text-slate-500">
                <p className="font-semibold mb-1">Routing thresholds</p>
                <div className="space-y-0.5">
                  <p><span className="text-green-600 font-medium">90–100</span> → Ready to Bill (auto_accept)</p>
                  <p><span className="text-amber-600 font-medium">50–89</span> → Needs Review (flag_for_review)</p>
                  <p><span className="text-red-500 font-medium">0–49</span> → Not Eligible (reject)</p>
                </div>
              </div>
            </div>
          )}

          {tab === 'missing' && (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                {missing.map(m => (
                  <span key={m} className="bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-1.5 rounded-full font-medium">
                    {m}
                  </span>
                ))}
              </div>

              {patient.missing_doc_request ? (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-semibold text-slate-700">Suggested Message to Clinician</p>
                    <CopyButton text={patient.missing_doc_request} />
                  </div>
                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
                    <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans leading-relaxed">
                      {patient.missing_doc_request}
                    </pre>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-slate-400 italic">No documentation gaps identified.</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">{title}</h3>
      {children}
    </div>
  )
}
