import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { KanbanColumn } from "./components/Kanban";
import { Metrics } from "./components/Metrics";
import { PipelinePanel } from "./components/PipelinePanel";
import { Sidebar } from "./components/Sidebar";
import type { Filters, Meta, Patient, RoutingDecision, Stats } from "./types";

const DEFAULT_FILTERS: Filters = {
  facilityId: null,
  routing: ["auto_accept", "flag_for_review", "reject"],
  submissionEligible: "all",
  missingFields: [],
  newAdmissionOnly: false,
  search: "",
};

export default function App() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [m, p, s] = await Promise.all([
        api.meta(),
        api.patients(filters),
        api.stats(filters),
      ]);
      setMeta(m);
      setPatients(p);
      setStats(s);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Cannot reach API — run: python run_api.py"
      );
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    load();
  }, [load]);

  const patchFilters = (patch: Partial<Filters>) => {
    setFilters((prev) => ({ ...prev, ...patch }));
  };

  const groups: Record<RoutingDecision, Patient[]> = {
    auto_accept: [],
    flag_for_review: [],
    reject: [],
  };
  for (const p of patients) {
    groups[p.routing_decision].push(p);
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar filters={filters} meta={meta} stats={stats} onChange={patchFilters} />

      <main className="flex-1 p-6 overflow-x-auto">
        <header className="mb-6">
          <h1 className="text-2xl font-bold tracking-tight">BillReady</h1>
          <p className="text-muted text-sm">Medicare Part B wound care billing worklist</p>
        </header>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-800 rounded-lg px-4 py-3 mb-4 text-sm">
            {error}
            <p className="mt-1 text-xs">Start backend: <code>python run_api.py</code></p>
          </div>
        )}

        {loading && !stats ? (
          <p className="text-muted">Loading…</p>
        ) : (
          <>
            <PipelinePanel onComplete={load} />
            <Metrics stats={stats} />
            <div className="flex gap-4">
              <KanbanColumn decision="auto_accept" patients={groups.auto_accept} meta={meta} />
              <KanbanColumn decision="flag_for_review" patients={groups.flag_for_review} meta={meta} />
              <KanbanColumn decision="reject" patients={groups.reject} meta={meta} />
            </div>
          </>
        )}
      </main>
    </div>
  );
}
