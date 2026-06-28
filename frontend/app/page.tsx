"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowRight,
  CircleNotch,
  Coins,
  Play,
  Stop,
  Terminal,
  WarningDiamond,
} from "@phosphor-icons/react";
import { BarList } from "@/components/ui/bar-list";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { StatusPill } from "@/components/ui/status-pill";
import { EventLog } from "@/components/event-log";
import { PageHeader } from "@/components/ui/page-header";
import { PipelineProgression } from "@/components/pipeline-progression";
import { usePipeline, useElapsedSeconds, type PipelineState } from "@/lib/use-pipeline";
import { num, pct, titleize } from "@/lib/utils";

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-0.5 truncate font-mono text-sm font-semibold tabular-nums text-foreground">
        {value}
      </p>
    </div>
  );
}

function SignalRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="font-mono text-sm tabular-nums text-foreground">{value}</span>
    </div>
  );
}

function SignalGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/70">
        {title}
      </p>
      <div className="divide-y divide-border/60 rounded-md border border-border bg-muted/20 px-3">
        {children}
      </div>
    </div>
  );
}

function RealtimeSignals({ state }: { state: PipelineState }) {
  const s = state.stats;
  const c = state.cascade;
  const d = state.decisions;
  const rows = state.counts
    ? Object.values(state.counts).reduce((a, b) => a + b, 0)
    : 0;
  const dash = "—";

  return (
    <div className="space-y-4">
      <SignalGroup title="Ingestion">
        <SignalRow label="Requests" value={s ? num(s.total_requests) : dash} />
        <SignalRow
          label="Rate limited (429)"
          value={s ? `${pct(s.observed_429_rate)} · ${num(s.rate_limited_429)}` : dash}
        />
        <SignalRow label="Calls / success" value={s ? s.calls_per_success.toFixed(2) : dash} />
      </SignalGroup>
      <SignalGroup title="Storage">
        <SignalRow label="Rows stored" value={rows ? num(rows) : dash} />
      </SignalGroup>
      <SignalGroup title="Extraction">
        <SignalRow label="Escalated to LLM" value={c ? num(c.escalated ?? 0) : dash} />
        <SignalRow label="LLM-enriched" value={c ? num(c.llm_enriched ?? 0) : dash} />
      </SignalGroup>
      <SignalGroup title="Routing">
        <SignalRow label="Auto-accept" value={d ? num(d.auto_accept ?? 0) : dash} />
        <SignalRow label="Flag for review" value={d ? num(d.flag_for_review ?? 0) : dash} />
        <SignalRow label="Reject" value={d ? num(d.reject ?? 0) : dash} />
      </SignalGroup>
    </div>
  );
}

export default function PipelinePage() {
  const { state, run, stop } = usePipeline();
  const running = state.status === "running";
  const elapsed = useElapsedSeconds(running, state.elapsed);

  const stats = state.stats;
  const report = state.report;
  const counts = state.counts;
  const patients = counts?.patients ?? report?.patients.total ?? 0;
  const records = state.stages.records;
  const traps = report
    ? report.notes.doubled_word_trap + report.assessments.laterality_conflict_trap
    : 0;
  const lastLine = state.log[state.log.length - 1]?.text;

  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] flex-col p-8 md:min-h-screen">
      <PageHeader
        eyebrow="ABI wound-care billing"
        title="Pipeline"
        description="Run the end-to-end pipeline and watch each stage stream live, from rate-limited PCC ingestion to billing decisions."
        actions={
          running ? (
            <Button variant="outline" onClick={stop}>
              <Stop className="h-4 w-4" weight="fill" />
              Stop
            </Button>
          ) : (
            <Button onClick={run}>
              <Play className="h-4 w-4" weight="fill" />
              Run pipeline
            </Button>
          )
        }
      />

      {/* Top: progression + KPIs + a one-line live event ticker */}
      <Card>
        <CardHeader className="flex-row items-center justify-between gap-4 space-y-0">
          <CardTitle className="text-base">Pipeline progression</CardTitle>
          <div className="flex items-center gap-2">
            {running && <CircleNotch className="h-4 w-4 animate-spin text-sky-500" />}
            <StatusPill
              status={state.status}
              label={state.status === "idle" ? "Idle" : undefined}
            />
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          <PipelineProgression state={state} />
          {state.error && <p className="text-sm text-destructive">{state.error}</p>}
          <div className="grid grid-cols-2 gap-4 border-t border-border pt-4 sm:grid-cols-4">
            <Stat label="Patients" value={patients ? num(patients) : "—"} />
            <Stat
              label="Records"
              value={records?.total ? `${num(records.done ?? 0)} / ${num(records.total)}` : "—"}
            />
            <Stat label="429 rate" value={stats ? pct(stats.observed_429_rate) : "—"} />
            <Stat label="Elapsed" value={state.status === "idle" ? "—" : `${elapsed.toFixed(1)}s`} />
          </div>
          {/* one-line live event ticker */}
          <div className="flex items-center gap-2 rounded-md border border-border bg-muted/30 px-3 py-2">
            {running ? (
              <CircleNotch className="h-3.5 w-3.5 shrink-0 animate-spin text-sky-500" />
            ) : (
              <Terminal className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            )}
            <span className="truncate font-mono text-xs text-muted-foreground">
              {lastLine ?? "Idle — press Run pipeline to start."}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Bottom: realtime signals (left) + raw event stream (right) */}
      <Card className="mt-6 flex flex-1 flex-col overflow-hidden">
        <CardHeader>
          <CardTitle className="text-base">Live run</CardTitle>
          <CardDescription>
            Realtime signals and the raw event stream as the pipeline executes.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid min-h-0 flex-1 gap-6 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <RealtimeSignals state={state} />
          </div>
          <div className="flex min-h-[20rem] flex-col overflow-hidden rounded-lg border border-border lg:col-span-3">
            <EventLog log={state.log} />
          </div>
        </CardContent>
      </Card>

      {/* Result snapshot */}
      {report && (
        <Card className="mt-6">
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-1.5">
                <CardTitle className="text-base">Data snapshot</CardTitle>
                <CardDescription>
                  Result of the latest characterization. Full breakdown under Signals.
                </CardDescription>
              </div>
              <Button asChild variant="ghost" size="sm">
                <Link href="/signals">
                  View signals
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            </div>
          </CardHeader>
          <CardContent className="grid gap-6 md:grid-cols-2">
            <div>
              <p className="mb-3 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                <Coins className="h-3.5 w-3.5" /> Payer mix
              </p>
              <BarList
                data={Object.entries(report.patients.primary_payer_mix)
                  .map(([k, v]) => ({ label: titleize(k), value: v }))
                  .sort((a, b) => b.value - a.value)}
                format={num}
              />
            </div>
            <div className="space-y-3">
              <p className="mb-3 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                <WarningDiamond className="h-3.5 w-3.5" /> Signal and traps
              </p>
              <div className="flex items-center justify-between rounded-md bg-muted/40 p-3 text-sm">
                <span className="text-muted-foreground">Billable (Medicare Part B)</span>
                <span className="font-mono font-semibold text-foreground">
                  {num(report.patients.billable_MCB)} ({report.patients.billable_MCB_pct}%)
                </span>
              </div>
              <div className="flex items-center justify-between rounded-md bg-muted/40 p-3 text-sm">
                <span className="text-muted-foreground">Active MCB coverage</span>
                <span className="font-mono font-semibold text-foreground">
                  {num(report.coverage.patients_with_active_MCB)}
                </span>
              </div>
              <div className="flex items-center justify-between rounded-md border border-border bg-muted/30 p-3 text-sm">
                <span className="flex items-center gap-2 text-muted-foreground">
                  <WarningDiamond className="h-4 w-4 text-amber-500" />
                  Dirty-data traps flagged
                </span>
                <span className="font-mono font-semibold text-foreground">{num(traps)}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
