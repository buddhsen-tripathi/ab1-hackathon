"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE } from "./api";
import type {
  DataReport,
  EligibilitySummary,
  ExtractionSummary,
  RequestStats,
} from "./types";

export type StageStatus = "idle" | "running" | "complete";

export interface StageState {
  status: StageStatus;
  done?: number;
  total?: number;
  message?: string;
}

export interface LogEntry {
  id: number;
  type: string;
  text: string;
  /** Entries sharing a key collapse into one rolling line (e.g. progress ticks). */
  key?: string;
}

export interface PipelineState {
  status: "idle" | "running" | "complete" | "error";
  stages: Record<string, StageState>;
  stats: RequestStats | null;
  counts: Record<string, number> | null;
  report: DataReport | null;
  cascade: Record<string, number> | null;
  extraction: ExtractionSummary | null;
  eligibility: EligibilitySummary | null;
  log: LogEntry[];
  elapsed: number | null;
  error: string | null;
}

export const STAGE_ORDER = [
  "roster",
  "records",
  "store",
  "characterize",
  "extract",
  "route",
] as const;

const STAGE_LABEL: Record<string, string> = {
  connect: "Connect",
  roster: "Fetch rosters",
  records: "Fetch records",
  store: "Store",
  characterize: "Characterize",
  extract: "Extract",
  route: "Route",
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Ev = { type: string; [k: string]: any };

function initialStages(): Record<string, StageState> {
  return Object.fromEntries(
    STAGE_ORDER.map((k) => [k, { status: "idle" as StageStatus }]),
  );
}

const INITIAL: PipelineState = {
  status: "idle",
  stages: initialStages(),
  stats: null,
  counts: null,
  report: null,
  cascade: null,
  extraction: null,
  eligibility: null,
  log: [],
  elapsed: null,
  error: null,
};

function describe(ev: Ev): string {
  const label = (s: string) => STAGE_LABEL[s] ?? s;
  switch (ev.type) {
    case "pipeline_start":
      return `Pipeline started — facilities ${(ev.facilities ?? []).join(", ")}`;
    case "stage_start":
      return `▶ ${label(ev.stage)}${ev.message ? ` — ${ev.message}` : ""}`;
    case "roster":
      return `   facility ${ev.facility}: ${ev.count} patients (total ${ev.running_total})`;
    case "progress": {
      let tail = "";
      if (ev.stage === "records") tail = ` · ${ev.stats?.rate_limited_429 ?? 0} × 429 retried`;
      else if (ev.stage === "extract" && ev.cascade)
        tail = ` · ${ev.cascade.escalated ?? 0} escalated`;
      return `   ${label(ev.stage)}: ${ev.done}/${ev.total}${tail}`;
    }
    case "stage_complete": {
      if (ev.stage === "extract" && ev.cascade) {
        const c = ev.cascade;
        return `✓ Extract complete — ${c.total ?? 0} docs · ${c.escalated ?? 0} escalated · ${c.llm_enriched ?? 0} LLM-enriched`;
      }
      if (ev.stage === "route" && ev.summary?.decisions) {
        const d = ev.summary.decisions;
        return `✓ Route complete — ${d.auto_accept ?? 0} auto · ${d.flag_for_review ?? 0} flag · ${d.reject ?? 0} reject`;
      }
      const extra = ev.total_patients
        ? ` — ${ev.total_patients} patients`
        : ev.counts
          ? ` — ${Object.values(ev.counts as Record<string, number>).reduce((a, b) => a + b, 0)} rows`
          : ev.done
            ? ` — ${ev.done} records`
            : "";
      return `✓ ${label(ev.stage)} complete${extra}`;
    }
    case "pipeline_complete":
      return `● Pipeline complete in ${ev.elapsed_sec}s — ${ev.stats?.total_requests} requests, ${Math.round((ev.stats?.observed_429_rate ?? 0) * 100)}% 429 rate`;
    case "error":
      return `✕ Error: ${ev.message}`;
    default:
      return ev.type;
  }
}

// Repeated progress ticks for one stage collapse into a single updating line,
// so the stream stays readable instead of scrolling hundreds of near-identical rows.
function appendLog(prev: LogEntry[], entry: LogEntry): LogEntry[] {
  const last = prev[prev.length - 1];
  if (entry.key && last && last.key === entry.key) {
    return [...prev.slice(0, -1), { ...entry, id: last.id }];
  }
  return [...prev, entry].slice(-250);
}

function reduce(s: PipelineState, ev: Ev, nextId: () => number): PipelineState {
  const key = ev.type === "progress" ? `progress:${ev.stage}` : undefined;
  const log = appendLog(s.log, { id: nextId(), type: ev.type, text: describe(ev), key });
  const stats = ev.stats ?? s.stats;

  switch (ev.type) {
    case "pipeline_start":
      return {
        ...s,
        status: "running",
        stages: initialStages(),
        cascade: null,
        extraction: null,
        eligibility: null,
        log,
        error: null,
        elapsed: null,
      };
    case "stage_start": {
      const stages = {
        ...s.stages,
        [ev.stage]: {
          status: "running" as StageStatus,
          message: ev.message,
          total: ev.total,
          done: 0,
        },
      };
      return { ...s, stages, log, stats };
    }
    case "roster":
      return { ...s, log, stats };
    case "progress": {
      const prev = s.stages[ev.stage] ?? { status: "running" as StageStatus };
      const stages = {
        ...s.stages,
        [ev.stage]: { ...prev, status: "running" as StageStatus, done: ev.done, total: ev.total },
      };
      return { ...s, stages, log, stats, cascade: ev.cascade ?? s.cascade };
    }
    case "stage_complete": {
      const prev = s.stages[ev.stage] ?? { status: "complete" as StageStatus };
      const stages = {
        ...s.stages,
        [ev.stage]: {
          ...prev,
          status: "complete" as StageStatus,
          done: prev.total ?? ev.done ?? prev.done,
        },
      };
      return {
        ...s,
        stages,
        counts: ev.counts ?? s.counts,
        cascade: ev.cascade ?? s.cascade,
        decisions: ev.summary?.decisions ?? s.decisions,
        log,
        stats,
      };
    }
    case "pipeline_complete":
      return {
        ...s,
        status: "complete",
        stats: ev.stats ?? stats,
        counts: ev.counts ?? s.counts,
        report: ev.data ?? s.report,
        cascade: ev.cascade ?? s.cascade,
        decisions: ev.eligibility?.decisions ?? s.decisions,
        elapsed: ev.elapsed_sec ?? null,
        log,
      };
    case "error":
      return { ...s, status: "error", error: ev.message ?? "Pipeline error", log };
    default:
      return { ...s, log, stats };
  }
}

export function usePipeline() {
  const [state, setState] = useState<PipelineState>(INITIAL);
  const esRef = useRef<EventSource | null>(null);
  const logId = useRef(0);

  // Seed idle-state display from a baseline /stats fetch (without starting a run).
  const seed = useCallback(
    (stats: RequestStats | null, report: DataReport | null, counts: Record<string, number> | null) => {
      setState((s) => (s.status === "idle" ? { ...s, stats, report, counts } : s));
    },
    [],
  );

  const stop = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    setState((s) => (s.status === "running" ? { ...s, status: "idle" } : s));
  }, []);

  const run = useCallback(() => {
    esRef.current?.close();
    logId.current = 0;
    setState({
      ...INITIAL,
      stages: initialStages(),
      status: "running",
      log: [{ id: 0, type: "connect", text: "Connecting to pipeline stream..." }],
    });

    const es = new EventSource(`${API_BASE}/pipeline/stream`);
    esRef.current = es;

    es.onmessage = (e) => {
      let ev: Ev;
      try {
        ev = JSON.parse(e.data);
      } catch {
        return;
      }
      setState((s) => reduce(s, ev, () => (logId.current += 1)));
      if (ev.type === "pipeline_complete" || ev.type === "error") {
        es.close();
        esRef.current = null;
      }
    };

    es.onerror = () => {
      setState((s) =>
        s.status === "running"
          ? { ...s, status: "error", error: `Stream disconnected. Is the backend running at ${API_BASE}?` }
          : s,
      );
      es.close();
      esRef.current = null;
    };
  }, []);

  useEffect(() => () => esRef.current?.close(), []);

  return { state, run, stop, seed };
}

export function useElapsedSeconds(active: boolean, finalValue: number | null) {
  const [sec, setSec] = useState(0);
  const start = useRef<number | null>(null);

  useEffect(() => {
    if (!active) return;
    start.current = Date.now();
    setSec(0);
    const id = setInterval(() => {
      if (start.current) setSec((Date.now() - start.current) / 1000);
    }, 100);
    return () => clearInterval(id);
  }, [active]);

  return finalValue ?? sec;
}
