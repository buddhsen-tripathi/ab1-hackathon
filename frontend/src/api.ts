import type { Filters, Meta, Patient, PatientDetail, Stats } from "./types";

export interface AppConfig {
  pcc_api_url: string;
  llm_available: boolean;
  llm_unavailable_reason: "missing_key" | "missing_package" | null;
  llm_model: string;
  llm_chunk_size: number;
  openai_setup: string;
}

export interface PipelineStep {
  id: string;
  label: string;
}

export interface PipelineStatus {
  state: "idle" | "running" | "completed" | "error";
  step: string | null;
  message: string;
  progress: number;
  logs: string[];
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  result: Record<string, unknown> | null;
  steps: PipelineStep[];
}

export interface PipelineRunOptions {
  clear_cache?: boolean;
  llm_verify?: boolean;
  use_cache?: boolean;
}

function buildParams(filters: Partial<Filters>): string {
  const p = new URLSearchParams();
  if (filters.facilityId) p.set("facility_id", String(filters.facilityId));
  if (filters.routing?.length) filters.routing.forEach((r) => p.append("routing_decision", r));
  if (filters.submissionEligible === "eligible") p.set("submission_eligible", "true");
  if (filters.submissionEligible === "not_eligible") p.set("submission_eligible", "false");
  if (filters.missingFields?.length)
    filters.missingFields.forEach((f) => p.append("missing_fields", f));
  if (filters.newAdmissionOnly) p.set("new_admission", "true");
  if (filters.search) p.set("search", filters.search);
  const qs = p.toString();
  return qs ? `?${qs}` : "";
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === "string" ? err.detail : `API error ${res.status}`);
  }
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === "string" ? err.detail : `API error ${res.status}`);
  }
  return res.json();
}

export const api = {
  config: () => get<AppConfig>("/api/config"),
  meta: () => get<Meta>("/api/meta"),
  patients: (filters: Partial<Filters>) => get<Patient[]>(`/api/patients${buildParams(filters)}`),
  stats: (filters: Partial<Filters>) => get<Stats>(`/api/stats${buildParams(filters)}`),
  patient: (id: string) => get<PatientDetail>(`/api/patients/${id}`),
  pipelineStatus: () => get<PipelineStatus>("/api/pipeline/status"),
  pipelineRun: (opts: PipelineRunOptions) => post<PipelineStatus>("/api/pipeline/run", opts),
};
