"use client";

import * as React from "react";
import {
  ArrowsClockwise,
  Brain,
  CheckCircle,
  CloudArrowDown,
  Database,
  Ruler,
  ShieldWarning,
  Sparkle,
  Warning,
  WarningDiamond,
  XCircle,
} from "@phosphor-icons/react";
import { BarList, type BarItem } from "@/components/ui/bar-list";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { AgentChat } from "@/components/ui/agent-chat";
import { KpiCard } from "@/components/ui/kpi-card";
import { LoadBoundary } from "@/components/ui/load-boundary";
import { PageHeader } from "@/components/ui/page-header";
import { StatusPill } from "@/components/ui/status-pill";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { num, pct, titleize } from "@/lib/utils";

function toBars(rec: Record<string, number>): BarItem[] {
  return Object.entries(rec)
    .map(([k, v]) => ({ label: titleize(k ?? "unknown"), value: v }))
    .sort((a, b) => b.value - a.value);
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-eyebrow uppercase text-muted-foreground">{children}</h2>
  );
}

function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="rounded-md bg-muted/40 p-3">
      <p className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-0.5 font-mono text-lg font-semibold tabular-nums text-foreground">{value}</p>
      {hint && <p className="mt-0.5 text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

const DECISION_COLORS: Record<string, string> = {
  auto_accept: "bg-emerald-500",
  flag_for_review: "bg-amber-500",
  reject: "bg-red-500",
};

/** Proportional auto / review / reject bar. */
function DecisionBar({ decisions }: { decisions: Record<string, number> }) {
  const order = ["auto_accept", "flag_for_review", "reject"];
  const total = order.reduce((s, k) => s + (decisions[k] ?? 0), 0) || 1;
  return (
    <div className="flex h-3 w-full overflow-hidden rounded-full bg-muted">
      {order.map((k) => {
        const v = decisions[k] ?? 0;
        return (
          <div
            key={k}
            className={DECISION_COLORS[k]}
            style={{ width: `${(v / total) * 100}%` }}
            title={`${titleize(k)}: ${v}`}
          />
        );
      })}
    </div>
  );
}

function TrapCard({
  count,
  title,
  description,
}: {
  count: number;
  title: string;
  description: string;
}) {
  return (
    <div className="flex items-start gap-3 rounded-md border border-border bg-muted/30 p-4">
      <WarningDiamond className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-semibold tabular-nums text-foreground">
            {num(count)}
          </span>
          <span className="text-sm font-medium text-foreground">{title}</span>
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}

export default function SignalsPage() {
  const { data, loading, error, reload } = useFetch(async () => {
    const [stats, extraction, eligibility, llm] = await Promise.all([
      api.stats(),
      api.extractionsSummary(),
      api.eligibilitySummary(),
      api.llmObservability(),
    ]);
    return { stats, extraction, eligibility, llm };
  });

  const rs = data?.stats.request_stats;
  const rep = data?.stats.data;
  const ex = data?.extraction;
  const el = data?.eligibility;
  const llm = data?.llm;

  const coverageBars: BarItem[] = ex
    ? Object.entries(ex.field_coverage_pct).map(([k, v]) => ({
        label: titleize(k),
        value: v,
      }))
    : [];

  return (
    <div className="p-8 pb-44">
      <PageHeader
        eyebrow="Methodology & outcome"
        title="Signals"
        description="How the pipeline turned 300 messy EHR records into billing decisions — the outcome first, then the reliability, extraction, and data-quality evidence behind it."
        actions={
          <Button variant="outline" size="sm" onClick={reload} disabled={loading}>
            <ArrowsClockwise className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            Refresh
          </Button>
        }
      />

      <LoadBoundary loading={loading} error={error} onRetry={reload}>
        {rs && rep && ex && el && (
          <div className="space-y-10">
            {/* ---- 1. Triage outcome (the punchline) ---- */}
            <section className="space-y-4">
              <SectionLabel>Triage outcome</SectionLabel>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
                <KpiCard label="Patients" value={num(el.total_patients)} hint="Across 3 facilities" icon={Database} />
                <KpiCard label="Billable (MCB)" value={num(el.active_mcb)} hint="Active Medicare Part B" icon={ShieldWarning} />
                <KpiCard label="Auto-accept" value={num(el.decisions.auto_accept ?? 0)} hint="Safe to route to billing" icon={CheckCircle} />
                <KpiCard label="Needs review" value={num(el.decisions.flag_for_review ?? 0)} hint="Ambiguous / incomplete" icon={Warning} />
                <KpiCard label="Reject" value={num(el.decisions.reject ?? 0)} hint="Not eligible / unparseable" icon={XCircle} />
              </div>
              <Card>
                <CardContent className="space-y-3 pt-6">
                  <DecisionBar decisions={el.decisions} />
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusPill status="auto_accept" label={`${el.decisions.auto_accept ?? 0} auto-accept`} />
                    <StatusPill status="flag_for_review" label={`${el.decisions.flag_for_review ?? 0} needs review`} />
                    <StatusPill status="reject" label={`${el.decisions.reject ?? 0} reject`} />
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Rejects are the {num(el.total_patients - el.active_mcb)} non-billable
                    patients (no active Part B). Of {num(el.active_mcb)} billable, {num(el.decisions.auto_accept ?? 0)} auto-accept
                    and {num(el.decisions.flag_for_review ?? 0)} are flagged for a human.
                  </p>
                </CardContent>
              </Card>
            </section>

            {/* ---- 2. Pipeline reliability ---- */}
            <section className="space-y-4">
              <SectionLabel>Pipeline reliability</SectionLabel>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <KpiCard label="Total requests" value={num(rs.total_requests)} hint="Last ingest run" icon={CloudArrowDown} />
                <KpiCard label="Rate limited (429)" value={pct(rs.observed_429_rate)} hint={`${num(rs.rate_limited_429)} retried away`} icon={Warning} />
                <KpiCard label="Calls / success" value={rs.calls_per_success.toFixed(2)} hint="Retry overhead (1/0.7 ≈ 1.43)" icon={ArrowsClockwise} />
                <KpiCard label="Permanent failures" value={num(rs.server_5xx + rs.net_errors)} hint="Retry drives this to zero" icon={CheckCircle} />
              </div>
            </section>

            {/* ---- 3. Extraction readiness ---- */}
            <section className="space-y-4">
              <SectionLabel>Extraction readiness</SectionLabel>
              <div className="grid gap-6 lg:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle>Field coverage</CardTitle>
                    <CardDescription>
                      Share of wound records where each billing field was extracted.
                      Depth is the gap — Envive narratives never state it.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <BarList data={coverageBars} format={(n) => `${n}%`} />
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>Source format mix</CardTitle>
                    <CardDescription>
                      {num(ex.total_wound_rows)} wound records parsed across structured
                      and free-text sources.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <BarList data={toBars(ex.by_source_format)} format={num} />
                    <div className="flex items-center justify-between rounded-md bg-muted/40 p-4">
                      <span className="text-sm text-muted-foreground">Billing-ready (per record)</span>
                      <span className="font-mono text-sm font-semibold text-foreground">
                        {num(ex.billing_ready)} ({ex.billing_ready_pct}%)
                      </span>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </section>

            {/* ---- LLM layer observability ---- */}
            {llm && (
              <section className="space-y-4">
                <SectionLabel>LLM layer</SectionLabel>
                <div className="grid gap-6 lg:grid-cols-2">
                  <Card>
                    <CardHeader>
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1.5">
                          <CardTitle>Confidence-gated escalation</CardTitle>
                          <CardDescription>
                            Heuristics and the knowledge base handle the confident
                            majority for free; only low-confidence or hard-format
                            documents escalate to the model.
                          </CardDescription>
                        </div>
                        <StatusPill
                          status={llm.config.enabled ? "live" : "inactive"}
                          label={llm.config.enabled ? "Enabled" : "Disabled"}
                        />
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="flex items-center justify-between rounded-md bg-muted/40 p-3 text-sm">
                        <span className="flex items-center gap-2 text-muted-foreground">
                          <Brain className="h-4 w-4" /> Model
                        </span>
                        <span className="font-mono text-xs text-foreground">
                          {llm.config.model}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <Stat
                          label="Escalated"
                          value={num(llm.cascade.escalated ?? 0)}
                          hint="hit the LLM gate"
                        />
                        <Stat
                          label="LLM-enriched"
                          value={num(llm.cascade.llm_enriched ?? 0)}
                          hint="fields resolved by model"
                        />
                        <Stat
                          label="LLM calls"
                          value={num(llm.config.stats.calls)}
                          hint={`${num(llm.config.stats.total_tokens)} tokens`}
                        />
                        <Stat
                          label="Avg confidence"
                          value={llm.avg_confidence.toFixed(2)}
                          hint="across extractions"
                        />
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Extraction method mix</CardTitle>
                      <CardDescription>
                        How each of {num(llm.total_wound_rows)} wound records was
                        resolved across the cascade.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {Object.keys(llm.method_distribution).length ? (
                        <BarList data={toBars(llm.method_distribution)} format={num} />
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          No extractions yet. Run the pipeline to populate this.
                        </p>
                      )}
                      <div className="flex items-start gap-3 rounded-md border border-border bg-muted/30 p-4">
                        <Sparkle className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
                        <p className="text-xs text-muted-foreground">
                          The KB cache makes the pipeline cheaper over time: identical
                          note text is memoized, and abbreviations or synonyms the LLM
                          resolves are written back so the next run handles them for free.
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </section>
            )}

            {/* ---- 4. Dirty-data traps caught ---- */}
            <section className="space-y-4">
              <SectionLabel>Dirty-data traps caught</SectionLabel>
              <div className="grid gap-6 lg:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle>Why patients need review</CardTitle>
                    <CardDescription>
                      Each flag is a defensible reason a human should look before billing.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {Object.keys(el.review_flags).length ? (
                      <BarList data={toBars(el.review_flags)} format={num} />
                    ) : (
                      <p className="text-sm text-muted-foreground">No review flags recorded.</p>
                    )}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>Extraction-level flags</CardTitle>
                    <CardDescription>
                      Traps detected while parsing notes &amp; assessments.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="grid gap-3">
                    <TrapCard
                      count={ex.flag_distribution.laterality_conflict ?? 0}
                      title="laterality conflicts"
                      description="Location side disagrees with the laterality field (e.g. left vs right)."
                    />
                    <TrapCard
                      count={ex.flag_distribution.multi_wound ?? 0}
                      title="multi-wound notes"
                      description="Two+ wounds described — the primary one is selected by largest area."
                    />
                    <TrapCard
                      count={rep.notes.doubled_word_trap}
                      title="doubled-word notes"
                      description="OCR-style repeats like 'stage stage 3' that break naive parsing."
                    />
                    <TrapCard
                      count={ex.flag_distribution.missing_depth ?? 0}
                      title="missing depth"
                      description="L × W documented but no depth — flagged unless another source supplies it."
                    />
                  </CardContent>
                </Card>
              </div>
              <div className="flex items-start gap-3 rounded-md border border-border bg-muted/30 p-4">
                <Ruler className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
                <p className="text-xs text-muted-foreground">
                  Cross-source conflicts (e.g. note says pressure ulcer, assessment says
                  arterial) are merged to fill gaps but flagged when the two sources
                  disagree — never silently overwritten.
                </p>
              </div>
            </section>
          </div>
        )}
      </LoadBoundary>

      {/* Agentic assistant, docked at the bottom of the page */}
      <AgentChat />
    </div>
  );
}
