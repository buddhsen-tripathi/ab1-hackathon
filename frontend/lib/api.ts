import type { StatsResponse, Patient, DbTablePage } from "./types";

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
  patients: (facilityId?: number) =>
    getJSON<Patient[]>(
      facilityId ? `/patients?facility_id=${facilityId}` : "/patients",
    ),
  dbTables: () => getJSON<Record<string, number>>("/db/tables"),
  dbTable: (name: string, limit = 50, offset = 0) =>
    getJSON<DbTablePage>(
      `/db/table/${name}?limit=${limit}&offset=${offset}`,
    ),
  ingest: async () => {
    const res = await fetch(`${API_BASE}/ingest`, { method: "POST" });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return (await res.json()) as { status: string };
  },
};
