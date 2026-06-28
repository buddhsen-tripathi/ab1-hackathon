"use client";

import * as React from "react";
import {
  ArrowsClockwise,
  CheckCircle,
  CloudArrowDown,
  Database,
  Drop,
  FileText,
  Ruler,
  ShieldWarning,
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
import { KpiCard } from "@/components/ui/kpi-card";
import { LoadBoundary } from "@/components/ui/load-boundary";
import { PageHeader } from "@/components/ui/page-header";
import { StatusPill } from "@/components/ui/status-pill";
import type { MeasurementDims } from "@/lib/types";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { num, pct, titleize } from "@/lib/utils";

function toBars(rec: Record<string, number>): BarItem[] {
  return Object.entries(rec)
    .map(([k, v]) => ({ label: titleize(k ?? "unknown"), value: v }))
    .sort((a, b) => b.value - a.value);
}

function dimsBars(d: MeasurementDims): BarItem[] {
  return [
    { label: "L × W × D (3D)", value: d.three_LxWxD },
    { label: "L × W only, depth missing", value: d.two_LxW_no_depth },
    { label: "None found", value: d.none_found },
  ];
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-eyebrow uppercase text-muted-foreground">{children}</h2>
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
  const { data, loading, error, reload } = useFetch(() => api.stats());
  const rs = data?.request_stats;
  const rep = data?.data;

  const retryAfter = rs
    ? Object.entries(rs.retry_after_distribution)
        .filter(([k]) => k !== "None")
        .sort((a, b) => Number(a[0]) - Number(b[0]))
        .map(([k, v]) => ({ label: `${k}s`, value: v }))
    : [];
  const countBars = rep
    ? Object.entries(rep.table_counts).map(([k, v]) => ({ label: titleize(k), value: v }))
    : [];

  return (
    <div className="p-8">
      <PageHeader
        eyebrow="Observability"
        title="Signals"
        description="Two kinds of signal from the last run: API request behavior (rate limiting, retries) and data-quality signals (formats, completeness, dirty-data traps)."
        actions={
          <Button variant="outline" size="sm" onClick={reload} disabled={loading}>
            <ArrowsClockwise className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            Refresh
          </Button>
        }
      />

      <LoadBoundary loading={loading} error={error} onRetry={reload}>
        {rs && rep && (
          <div className="space-y-10">
            {/* ---- Request signals ---- */}
            <section className="space-y-4">
              <SectionLabel>Request signals</SectionLabel>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <KpiCard label="Total requests" value={num(rs.total_requests)} hint="This server session" icon={CloudArrowDown} />
                <KpiCard label="Delivered (200)" value={num(rs.ok)} hint="Successful responses" icon={CheckCircle} />
                <KpiCard label="Rate limited (429)" value={num(rs.rate_limited_429)} hint={`${pct(rs.observed_429_rate)} observed`} icon={Warning} />
                <KpiCard label="Calls / success" value={rs.calls_per_success.toFixed(3)} hint="Retry overhead" icon={XCircle} />
              </div>

              <div className="grid gap-6 lg:grid-cols-3">
                <Card className="lg:col-span-2">
                  <CardHeader>
                    <CardTitle>Retry strategy</CardTitle>
                    <CardDescription>
                      Each request fails independently with p ≈ 0.30, so retrying drives
                      the per-record failure probability to near zero.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="rounded-md bg-muted/50 p-4 font-mono text-xs leading-relaxed text-muted-foreground">
                      P(still failing after k tries) = 0.30^k
                      <br />
                      {"  k=1  →  30.0%"}
                      <br />
                      {"  k=3  →   2.7%"}
                      <br />
                      {"  k=6  →   0.07%"}
                      <br />
                      {"  k=12 →   0.0000005%"}
                    </p>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <StatusPill status="ok" label="200 delivered" />
                      <StatusPill status="pending" label="429 retried" />
                      <StatusPill status="error" label="5xx / net err" />
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Retry-After</CardTitle>
                    <CardDescription>Server back-off hints (seconds).</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {retryAfter.length ? (
                      <BarList data={retryAfter} format={num} />
                    ) : (
                      <p className="text-sm text-muted-foreground">No 429s recorded yet.</p>
                    )}
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>Stored records</CardTitle>
                  <CardDescription>Row counts per table after the run.</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-6 md:grid-cols-2">
                  <BarList data={countBars} format={num} />
                  <div className="flex items-center gap-3 rounded-md bg-muted/40 p-4">
                    <Database className="h-5 w-5 shrink-0 text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">
                      Full raw JSON is kept per row so nothing is lost. Promoted columns
                      make characterization queries fast.
                    </p>
                  </div>
                </CardContent>
              </Card>
            </section>

            {/* ---- Data signals ---- */}
            <section className="space-y-4">
              <SectionLabel>Data signals</SectionLabel>

              <div className="grid gap-6 lg:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle>Payer mix</CardTitle>
                    <CardDescription>
                      Only Medicare Part B (MCB) is billable for wound care.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <BarList data={toBars(rep.patients.primary_payer_mix)} format={num} />
                    <div className="flex items-center justify-between rounded-md bg-muted/40 p-4">
                      <span className="text-sm text-muted-foreground">Billable (MCB)</span>
                      <span className="font-mono text-sm font-semibold text-foreground">
                        {num(rep.patients.billable_MCB)} ({rep.patients.billable_MCB_pct}%)
                      </span>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Coverage signal</CardTitle>
                    <CardDescription>Confirming active Part B is harder than it looks.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between rounded-md bg-muted/40 p-4">
                      <span className="text-sm text-muted-foreground">Patients with active MCB</span>
                      <span className="font-mono text-sm font-semibold text-foreground">
                        {num(rep.coverage.patients_with_active_MCB)}
                      </span>
                    </div>
                    <BarList data={toBars(rep.coverage.payer_type_distribution)} format={num} />
                    <div className="flex items-start gap-3 rounded-md border border-border bg-muted/30 p-4">
                      <ShieldWarning className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
                      <p className="text-xs text-muted-foreground">{rep.coverage.note}</p>
                    </div>
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>Progress notes</CardTitle>
                  <CardDescription>
                    {num(rep.notes.total)} current notes. Format drives extraction reliability.
                  </CardDescription>
                </CardHeader>
                <CardContent className="grid gap-6 lg:grid-cols-3">
                  <div>
                    <p className="mb-3 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      <FileText className="h-3.5 w-3.5" /> Format family
                    </p>
                    <BarList data={toBars(rep.notes.format_family)} format={num} />
                  </div>
                  <div>
                    <p className="mb-3 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      <Ruler className="h-3.5 w-3.5" /> Measurement completeness
                    </p>
                    <BarList data={dimsBars(rep.notes.measurement_dims)} format={num} />
                  </div>
                  <div className="space-y-3">
                    <p className="mb-3 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      <Drop className="h-3.5 w-3.5" /> Signal and traps
                    </p>
                    <div className="flex items-center justify-between rounded-md bg-muted/40 p-3 text-sm">
                      <span className="text-muted-foreground">Drainage keyword found</span>
                      <span className="font-mono font-semibold text-foreground">
                        {num(rep.notes.drainage_keyword_found)}
                      </span>
                    </div>
                    <TrapCard
                      count={rep.notes.doubled_word_trap}
                      title="doubled-word notes"
                      description="OCR-style repeats like 'stage stage 3' that break naive parsing."
                    />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Structured assessments</CardTitle>
                  <CardDescription>
                    {num(rep.assessments.total)} assessments. Mostly structured JSON, some narrative blobs.
                  </CardDescription>
                </CardHeader>
                <CardContent className="grid gap-6 lg:grid-cols-3">
                  <div>
                    <p className="mb-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      raw_json shape
                    </p>
                    <BarList data={toBars(rep.assessments.raw_json_shape)} format={num} />
                  </div>
                  <div>
                    <p className="mb-3 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      <Ruler className="h-3.5 w-3.5" /> Measurement completeness
                    </p>
                    <BarList data={dimsBars(rep.assessments.measurement_dims)} format={num} />
                  </div>
                  <div className="space-y-3">
                    <p className="mb-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Traps
                    </p>
                    <TrapCard
                      count={rep.assessments.laterality_conflict_trap}
                      title="laterality conflicts"
                      description="'Location' side disagrees with the 'Laterality' field, e.g. left vs right."
                    />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Note samples by format</CardTitle>
                  <CardDescription>One representative note per detected format.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {Object.entries(rep.notes.samples_by_format).map(([fmt, sample]) => (
                    <div key={fmt} className="space-y-2">
                      <StatusPill status="neutral" label={titleize(fmt)} />
                      <pre className="overflow-x-auto rounded-md bg-muted/50 p-4 font-mono text-xs leading-relaxed text-muted-foreground">
                        {sample}
                      </pre>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </section>
          </div>
        )}
      </LoadBoundary>
    </div>
  );
}
