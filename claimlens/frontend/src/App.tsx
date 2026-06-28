import React, { useState, useEffect, useCallback } from 'react'
import { Patient, Stats, SyncStatus, RoutingDecision } from './types'
import { MetricCards } from './components/MetricCards'
import { PatientTable } from './components/PatientTable'
import { PatientDrawer } from './components/PatientDrawer'
import { ApiHealthMonitor } from './components/ApiHealthMonitor'
import { SyncBar } from './components/SyncBar'
import { Bot, CheckCircle2, CloudCog, Database, Search, ShieldCheck, TriangleAlert } from 'lucide-react'

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
      await fetch('/api/sync?incremental=true&use_llm=true', { method: 'POST' })
      setSyncStatus({
        running: true,
        total: 0,
        processed: 0,
        errors: 0,
        started_at: new Date().toISOString(),
        status: 'running',
        current_step: 'Checking PCC for changes...',
        mode: stats?.last_sync ? 'incremental' : 'full',
        since: stats?.last_sync || null,
        changed_patients: 0,
      })
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

  return (
    <div className="min-h-screen app-shell flex flex-col">
      {/* Top nav */}
      <header className="app-header flex-shrink-0">
        <div className="max-w-[1480px] mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <div className="brand-mark" aria-hidden="true"><ShieldCheck size={19} strokeWidth={2.2} /></div>
              <div>
                <h1 className="text-lg font-semibold">ClaimLens AI</h1>
                <p className="hidden sm:block text-xs text-slate-400">Evidence-backed Part B wound billing control</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {backendDown && (
              <div className="status-chip status-chip-danger">
                <TriangleAlert size={14} /> Backend offline
              </div>
            )}
            <SyncBar status={syncStatus} onSync={handleSync} />
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-[1480px] mx-auto w-full px-4 sm:px-6 py-5 space-y-4">

        <section className="system-strip" aria-label="System capabilities">
          <div className="system-item">
            <Database size={15} />
            <span>PCC pipeline</span>
            <strong>{backendDown ? 'Offline' : 'Connected'}</strong>
          </div>
          <div className="system-item">
            <CloudCog size={15} />
            <span>Sync mode</span>
            <strong>{stats?.incremental_sync_ready ? 'Incremental ready' : 'Full refresh required'}</strong>
          </div>
          <div className="system-item">
            <Bot size={15} />
            <span>Claude assist</span>
            <strong className={stats?.llm_configured ? 'text-emerald-700' : 'text-amber-700'}>
              {stats?.llm_configured ? 'Configured' : 'Key required'}
            </strong>
          </div>
          <div className="system-item hidden lg:flex">
            <CheckCircle2 size={15} />
            <span>Last run</span>
            <strong>{stats?.last_sync_mode ? `${stats.last_sync_mode} · ${stats.last_sync_count} updated` : 'Not synced'}</strong>
          </div>
        </section>

        {/* Metric cards */}
        <MetricCards stats={stats} />

        {/* Work queue */}
        <section className="queue-panel">
          {/* Queue header */}
          <div className="border-b border-slate-200 px-5 pt-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
              <div>
                <h2 className="font-semibold text-slate-900">Claim work queue</h2>
                <p className="text-xs text-slate-500 mt-0.5">Prioritized by readiness score and documentation risk</p>
              </div>
              <div className="relative">
                <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search patient, wound type..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="search-input"
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
                        : stats.docs_gap_count}
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
        </section>

        {/* API health */}
        {stats?.api_health && stats.api_health.total_requests > 0 && (
          <ApiHealthMonitor health={stats.api_health} lastSync={stats.last_sync} />
        )}

        {/* Empty state: no data yet */}
        {!loading && stats?.total_patients === 0 && !backendDown && (
          <div className="bg-sky-50 border border-sky-200 rounded-lg p-6 text-center">
            <Database className="mx-auto mb-2 text-sky-600" size={28} />
            <p className="font-semibold text-sky-800 mb-1">No patient data yet</p>
            <p className="text-sm text-sky-600 mb-4">Click "Sync Data" to pull 300 patients from the PCC API across 3 facilities.</p>
            <button
              onClick={handleSync}
              className="bg-sky-600 hover:bg-sky-700 text-white text-sm font-semibold px-6 py-2.5 rounded-lg shadow-sm transition-colors"
            >
              Start full sync
            </button>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white px-6 py-3 flex-shrink-0">
        <div className="max-w-[1480px] mx-auto flex flex-col sm:flex-row gap-1 items-center justify-between text-xs text-slate-500">
          <span>No black-box routing. Every decision is backed by source-level evidence.</span>
          <span>Claude assisted · PCC connected · Synthetic data only</span>
        </div>
      </footer>

      {/* Patient detail drawer */}
      {selected && (
        <PatientDrawer patient={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
