import type {
  StatsResponse,
  Patient,
  DbTablePage,
  ExtractionSummary,
  EligibilitySummary,
  EligibilityResult,
  LlmObservability,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export const api = {
  base: API_BASE,
  health: () => getJSON<{ status: string }>("/health"),
  stats: () => getJSON<StatsResponse>("/stats"),
  extractionsSummary: () => getJSON<ExtractionSummary>("/extractions/summary"),
  eligibilitySummary: () => getJSON<EligibilitySummary>("/eligibility/summary"),
  llmObservability: () => getJSON<LlmObservability>("/llm/observability"),
  patients: (facilityId?: number) =>
    getJSON<Patient[]>(
      facilityId ? `/patients?facility_id=${facilityId}` : "/patients",
    ),
  dbTables: () => getJSON<Record<string, number>>("/db/tables"),
  dbTable: (
    name: string,
    limit = 50,
    offset = 0,
    opts?: { search?: string; facilityId?: number | null },
  ) => {
    const q = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (opts?.search) q.set("search", opts.search);
    if (opts?.facilityId != null) q.set("facility_id", String(opts.facilityId));
    return getJSON<DbTablePage>(`/db/table/${name}?${q.toString()}`);
  },
  eligibility: (filters?: {
    decision?: string | null;
    facilityId?: number | null;
    search?: string;
    eligible?: boolean | null;
    newAdmission?: boolean | null;
    missing?: string | null;
  }) => {
    const q = new URLSearchParams();
    if (filters?.decision) q.set("decision", filters.decision);
    if (filters?.facilityId != null) q.set("facility_id", String(filters.facilityId));
    if (filters?.search) q.set("search", filters.search);
    if (filters?.eligible != null) q.set("eligible", String(filters.eligible));
    if (filters?.newAdmission != null) q.set("new_admission", String(filters.newAdmission));
    if (filters?.missing) q.set("missing", filters.missing);
    const qs = q.toString();
    return getJSON<EligibilityResult[]>(`/eligibility${qs ? `?${qs}` : ""}`);
  },
  ingest: async () => {
    const res = await fetch(`${API_BASE}/ingest`, { method: "POST" });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return (await res.json()) as { status: string };
  },
};
