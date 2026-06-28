"use client";

import * as React from "react";
import { X } from "@phosphor-icons/react";
import { LoadBoundary } from "@/components/ui/load-boundary";
import { StatusPill } from "@/components/ui/status-pill";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import type { WoundExtractionRow } from "@/lib/types";
import { cn, titleize } from "@/lib/utils";

function s(v: unknown): string {
  return v == null || v === "" ? "—" : String(v);
}

function dimsOf(l: number | null, w: number | null, d: number | null): string {
  if (l == null && w == null && d == null) return "—";
  return [l, w, d].map((x) => (x == null ? "—" : x)).join(" × ") + " cm";
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
      {children}
    </h3>
  );
}

function FieldGrid({ rows }: { rows: [string, React.ReactNode][] }) {
  return (
    <div className="grid grid-cols-[110px_1fr] gap-x-4 gap-y-1.5 text-sm">
      {rows.map(([k, v]) => (
        <React.Fragment key={k}>
          <span className="text-muted-foreground">{k}</span>
          <span className="text-foreground">{v}</span>
        </React.Fragment>
      ))}
    </div>
  );
}

function ExtractionCard({ e }: { e: WoundExtractionRow }) {
  const summary = [
    e.wound_type && titleize(e.wound_type),
    e.stage && `stage ${e.stage}`,
    e.location,
    e.length_cm != null ? dimsOf(e.length_cm, e.width_cm, e.depth_cm) : null,
    e.drainage_amount && `${e.drainage_amount} drainage`,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="space-y-2 rounded-md border border-border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill
          status={e.is_primary ? "active" : "neutral"}
          label={e.is_primary ? "primary" : "secondary"}
        />
        <span className="text-xs font-medium text-foreground">
          {titleize(e.source_format)}
        </span>
        <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
          {e.method}
        </span>
        {e.method === "llm" && (
          <span className="rounded bg-violet-100 px-1.5 py-0.5 text-[10px] font-medium text-violet-700 dark:bg-violet-500/15 dark:text-violet-400">
            AI
          </span>
        )}
        <span className="ml-auto font-mono text-xs text-muted-foreground">
          {Math.round((e.confidence || 0) * 100)}%
        </span>
      </div>
      <div className="text-xs text-muted-foreground">{summary || "—"}</div>
      {e.flags?.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {e.flags.map((f) => (
            <span
              key={f}
              className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] text-amber-700 dark:bg-amber-500/15 dark:text-amber-400"
            >
              {titleize(f)}
            </span>
          ))}
        </div>
      )}
      {e.raw_span && (
        <pre className="overflow-x-auto whitespace-pre-wrap rounded bg-muted/50 p-2 text-[11px] leading-relaxed text-muted-foreground">
          {e.raw_span}
        </pre>
      )}
    </div>
  );
}

/** Render an assessment's raw_json transparently: structured Q/A, flat object,
 *  or the raw string — never hiding what the parser actually saw. */
function AssessmentBody({ raw }: { raw: string | null }) {
  if (!raw) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return <p className="whitespace-pre-wrap text-xs text-muted-foreground">{raw}</p>;
  }
  const obj = parsed as Record<string, unknown>;
  const sections = obj?.sections as
    | { sectionName?: string; questions?: { question?: string; answer?: unknown }[] }[]
    | undefined;
  if (Array.isArray(sections)) {
    return (
      <FieldGrid
        rows={sections.flatMap((sec) =>
          (sec.questions ?? []).map(
            (q) => [q.question ?? "—", s(q.answer)] as [string, React.ReactNode],
          ),
        )}
      />
    );
  }
  if (parsed && typeof parsed === "object") {
    return (
      <FieldGrid
        rows={Object.entries(obj).map(([k, v]) => [k, s(v)] as [string, React.ReactNode])}
      />
    );
  }
  return <p className="whitespace-pre-wrap text-xs text-muted-foreground">{String(parsed)}</p>;
}

function NoteText({ text }: { text: string | null }) {
  const [open, setOpen] = React.useState(false);
  if (!text) return <span className="text-xs text-muted-foreground">—</span>;
  const long = text.length > 320;
  const shown = open || !long ? text : text.slice(0, 320) + "…";
  return (
    <p className="whitespace-pre-wrap text-xs leading-relaxed text-muted-foreground">
      {shown}
      {long && (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="ml-1 text-primary hover:underline"
        >
          {open ? "Show less" : "Show more"}
        </button>
      )}
    </p>
  );
}

export function PatientDetail({
  patientId,
  onClose,
}: {
  patientId: string;
  onClose: () => void;
}) {
  const { data, loading, error, reload } = useFetch(
    () => api.eligibilityDetail(patientId),
    [patientId],
  );

  React.useEffect(() => {
    const onKey = (ev: KeyboardEvent) => ev.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const r = data?.result;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="h-full w-full max-w-xl overflow-y-auto border-l border-border bg-background shadow-2xl"
        onClick={(ev) => ev.stopPropagation()}
      >
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-background px-6 py-4">
          <div>
            <div className="font-mono text-sm text-foreground">{patientId}</div>
            {r && (
              <div className="text-xs text-muted-foreground">
                {[r.first_name, r.last_name].filter(Boolean).join(" ") || "—"} ·
                Facility {r.facility_id}
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6">
          <LoadBoundary loading={loading} error={error} onRetry={reload}>
            {data && r && (
              <div className="space-y-6">
                {/* Decision */}
                <section className="space-y-2">
                  <StatusPill status={r.routing_decision} />
                  <p className="text-sm text-muted-foreground">{r.reason}</p>
                </section>

                {/* Routed decision fields */}
                <section>
                  <SectionTitle>Routed decision</SectionTitle>
                  <FieldGrid
                    rows={[
                      ["Wound", r.wound_type ? titleize(r.wound_type) : "—"],
                      ["Stage", s(r.stage)],
                      ["Location", `${s(r.location)}${r.laterality ? ` (${r.laterality})` : ""}`],
                      ["Size", dimsOf(r.length_cm, r.width_cm, r.depth_cm)],
                      ["Drainage", s(r.drainage_amount)],
                      ["MCB", r.has_active_mcb ? "active" : "none"],
                      ["Source", s(r.extraction_source)],
                      ["Confidence", `${Math.round((r.extraction_confidence || 0) * 100)}%`],
                    ]}
                  />
                </section>

                {/* Diagnoses (ties to the ICD-10 gate) */}
                <section>
                  <SectionTitle>Diagnoses on record ({data.diagnoses.length})</SectionTitle>
                  <ul className="space-y-1 text-sm">
                    {data.diagnoses.map((d, i) => (
                      <li key={i} className="flex items-baseline gap-2">
                        <span className="font-mono text-xs text-foreground">
                          {s(d.icd10_code)}
                        </span>
                        <span className="text-muted-foreground">{s(d.icd10_description)}</span>
                        <span
                          className={cn(
                            "ml-auto text-[10px]",
                            d.clinical_status === "active"
                              ? "text-emerald-600 dark:text-emerald-400"
                              : "text-muted-foreground",
                          )}
                        >
                          {s(d.clinical_status)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>

                {/* Coverage */}
                <section>
                  <SectionTitle>Coverage</SectionTitle>
                  <ul className="space-y-1 text-sm">
                    {data.coverage.map((c, i) => (
                      <li key={i} className="flex items-baseline gap-2">
                        <span className="font-mono text-xs text-foreground">{s(c.payer_code)}</span>
                        <span className="text-muted-foreground">{s(c.payer_name ?? c.payer_type)}</span>
                        <span className="ml-auto text-[10px] text-muted-foreground">
                          {c.effective_to ? `ends ${s(c.effective_to)}` : "active"}
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>

                {/* Wound evidence (incl. secondary wounds — the multi-wound story) */}
                <section className="space-y-2">
                  <SectionTitle>
                    Wound evidence — {data.extractions.length} source
                    {data.extractions.length === 1 ? "" : "s"}
                    {r.secondary_wound_count > 0 &&
                      ` · ${r.secondary_wound_count} other wound${r.secondary_wound_count === 1 ? "" : "s"} present`}
                  </SectionTitle>
                  {data.extractions.map((e) => (
                    <ExtractionCard key={e.id} e={e} />
                  ))}
                </section>

                {/* Raw assessment(s) — verify the extraction against source */}
                {data.assessments.length > 0 && (
                  <section className="space-y-2">
                    <SectionTitle>Assessment ({data.assessments.length})</SectionTitle>
                    {data.assessments.map((a, i) => (
                      <div key={i} className="space-y-1.5 rounded-md border border-border p-3">
                        <div className="flex items-baseline justify-between">
                          <span className="text-xs font-medium text-foreground">
                            {s(a.assessment_type)}
                          </span>
                          <span className="text-[10px] text-muted-foreground">
                            {s(a.assessment_date)}
                          </span>
                        </div>
                        <AssessmentBody raw={(a.raw_json as string | null) ?? null} />
                      </div>
                    ))}
                  </section>
                )}

                {/* Raw clinical notes — the free text the pipeline parsed */}
                {data.notes.length > 0 && (
                  <section className="space-y-2">
                    <SectionTitle>Clinical notes ({data.notes.length})</SectionTitle>
                    {data.notes.map((n, i) => (
                      <div key={i} className="space-y-1 rounded-md border border-border p-3">
                        <div className="flex items-baseline justify-between">
                          <span className="text-xs font-medium text-foreground">
                            {s(n.note_type)}
                          </span>
                          <span className="text-[10px] text-muted-foreground">
                            {s(n.effective_date)}
                          </span>
                        </div>
                        {n.created_by != null && (
                          <p className="text-[10px] text-muted-foreground">By: {s(n.created_by)}</p>
                        )}
                        <NoteText text={(n.note_text as string | null) ?? null} />
                      </div>
                    ))}
                  </section>
                )}
              </div>
            )}
          </LoadBoundary>
        </div>
      </div>
    </div>
  );
}
