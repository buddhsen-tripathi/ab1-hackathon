import React, { useState, useEffect, useCallback } from 'react'
import { Patient, Stats, SyncStatus, RoutingDecision } from './types'
import { MetricCards } from './components/MetricCards'
import { PatientTable } from './components/PatientTable'
import { PatientDrawer } from './components/PatientDrawer'
import { ApiHealthMonitor } from './components/ApiHealthMonitor'
import { SyncBar } from './components/SyncBar'
import { DecisionBadge } from './components/DecisionBadge'

type Tab = 'all' | 'auto_accept' | 'flag_for_review' | 'reject' | 'missing_docs'

const TABS: { id: Tab; label: string; color: string }[] = [
  { id: 'all', label: 'All Patients', color: 'text-slate-600' },
  { id: 'auto_accept', label: 'Ready to Bill', color: 'text-green-600' },
  { id: 'flag_for_review', label: 'Needs Review', color: 'text-amber-600' },
  { id: 'reject', label: 'Not Eligible', color: 'text-red-500' },
  { id: 'missing_docs', label: 'Missing Docs', color: 'text-violet-600' },
]

const API = ''  // proxied via vite

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export default function App() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [patients, setPatients] = useState<Patient[]>([])
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<Tab>('all')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Patient | null>(null)
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null)
  const [backendDown, setBackendDown] = useState(false)

  const loadStats = useCallback(async () => {
    try {
      const s = await apiFetch<Stats>('/api/stats')
      setStats(s)
      setBackendDown(false)
    } catch {
      setBackendDown(true)
    }
  }, [])

  const loadPatients = useCallback(async () => {
    setLoading(true)
    try {
      const decision = activeTab === 'all' || activeTab === 'missing_docs' ? undefined : activeTab
      const qs = new URLSearchParams()
      if (decision) qs.set('routing_decision', decision)
      if (search) qs.set('search', search)
      let data = await apiFetch<Patient[]>(`/api/patients?${qs}`)
      if (activeTab === 'missing_docs') {
        data = data.filter(p => (p.missing_fields || []).length > 0)
      }
      setPatients(data)
    } catch {
      setPatients([])
    } finally {
      setLoading(false)
    }
  }, [activeTab, search])

  const pollSyncStatus = useCallback(async () => {
    try {
      const s = await apiFetch<SyncStatus>('/api/sync/status')
      setSyncStatus(s)
      return s
    } catch {
      return null
    }
  }, [])

  const handleSync = async () => {
    try {
      await fetch('/api/sync', { method: 'POST' })
      setSyncStatus(prev => ({ ...prev!, running: true, status: 'running', current_step: 'Starting...' }))
    } catch {}
  }

  // Poll sync status while running; refresh patients every 10 polls
  useEffect(() => {
    if (!syncStatus?.running) return
    let pollCount = 0
    const id = setInterval(async () => {
      const s = await pollSyncStatus()
      pollCount++
      // Refresh stats every poll, patients every 5 polls during sync
      await loadStats()
      if (pollCount % 5 === 0) await loadPatients()
      if (!s?.running) {
        clearInterval(id)
        await loadPatients()
      }
    }, 1500)
    return () => clearInterval(id)
  }, [syncStatus?.running])

  // Initial load
  useEffect(() => {
    loadStats()
    pollSyncStatus()
  }, [])

  useEffect(() => {
    loadPatients()
  }, [activeTab, search])

  // Refresh stats every 30s
  useEffect(() => {
    const id = setInterval(loadStats, 30000)
    return () => clearInterval(id)
  }, [])

  const tabCounts: Record<Tab, number> = {
    all: stats?.total_patients || 0,
    auto_accept: stats?.auto_accept || 0,
    flag_for_review: stats?.flag_for_review || 0,
    reject: stats?.reject || 0,
    missing_docs: patients.filter(p => (p.missing_fields || []).length > 0 && activeTab === 'missing_docs').length || 0,
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Top nav */}
      <header className="bg-slate-900 text-white px-6 py-4 shadow-lg flex-shrink-0">
        <div className="max-w-screen-xl mx-auto flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-sky-500 rounded-lg flex items-center justify-center font-bold text-sm">CL</div>
              <div>
                <h1 className="text-xl font-bold tracking-tight">ClaimLens AI</h1>
                <p className="text-xs text-slate-400">Evidence-backed Medicare Part B wound care billing triage</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {backendDown && (
              <div className="bg-red-900/50 border border-red-700 text-red-300 text-xs px-3 py-1.5 rounded-lg">
                ⚠ Backend offline — start the FastAPI server
              </div>
            )}
            <SyncBar status={syncStatus} onSync={handleSync} />
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-screen-xl mx-auto w-full px-6 py-5 space-y-5">

        {/* Metric cards */}
        <MetricCards stats={stats} />

        {/* Work queue */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          {/* Queue header */}
          <div className="border-b border-slate-200 px-5 pt-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-bold text-slate-900">Claim Work Queue</h2>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">🔍</span>
                <input
                  type="text"
                  placeholder="Search patient, wound type..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="pl-8 pr-4 py-1.5 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-300 focus:border-sky-400 w-64"
                />
              </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-0 overflow-x-auto">
              {TABS.map(t => (
                <button
                  key={t.id}
                  onClick={() => setActiveTab(t.id)}
                  className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                    activeTab === t.id
                      ? `border-sky-500 ${t.color}`
                      : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
                  }`}
                >
                  {t.label}
                  {stats && (
                    <span className={`text-xs px-1.5 py-0.5 rounded-full font-semibold ${
                      activeTab === t.id ? 'bg-sky-100 text-sky-700' : 'bg-slate-100 text-slate-500'
                    }`}>
                      {t.id === 'all' ? stats.total_patients
                        : t.id === 'auto_accept' ? stats.auto_accept
                        : t.id === 'flag_for_review' ? stats.flag_for_review
                        : t.id === 'reject' ? stats.reject
                        : patients.filter(p => (p.missing_fields||[]).length > 0).length}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Table */}
          <div className="overflow-auto max-h-[calc(100vh-380px)]">
            <PatientTable
              patients={patients}
              onSelect={setSelected}
              loading={loading}
            />
          </div>
        </div>

        {/* API health */}
        {stats?.api_health && stats.api_health.total_requests > 0 && (
          <ApiHealthMonitor health={stats.api_health} lastSync={stats.last_sync} />
        )}

        {/* Empty state: no data yet */}
        {!loading && stats?.total_patients === 0 && !backendDown && (
          <div className="bg-sky-50 border border-sky-200 rounded-xl p-6 text-center">
            <p className="text-2xl mb-2">🚀</p>
            <p className="font-semibold text-sky-800 mb-1">No patient data yet</p>
            <p className="text-sm text-sky-600 mb-4">Click "Sync Data" to pull 300 patients from the PCC API across 3 facilities.</p>
            <button
              onClick={handleSync}
              className="bg-sky-600 hover:bg-sky-700 text-white text-sm font-semibold px-6 py-2.5 rounded-lg shadow-sm transition-colors"
            >
              Start Sync →
            </button>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white px-6 py-3 flex-shrink-0">
        <div className="max-w-screen-xl mx-auto flex items-center justify-between text-xs text-slate-400">
          <span>ClaimLens AI · ABI Hackathon · No black-box routing — every decision is backed by source-level evidence.</span>
          <span>Powered by Claude + PCC Mock API</span>
        </div>
      </footer>

      {/* Patient detail drawer */}
      {selected && (
        <PatientDrawer patient={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
