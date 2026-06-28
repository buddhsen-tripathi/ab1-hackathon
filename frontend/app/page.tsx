"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowRight, CircleNotch, Coins, Play, Stop, WarningDiamond } from "@phosphor-icons/react";
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
import { LiveStepper } from "@/components/live-stepper";
import { PageHeader } from "@/components/ui/page-header";
import { PipelineProgression } from "@/components/pipeline-progression";
import { usePipeline, useElapsedSeconds } from "@/lib/use-pipeline";
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

  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] flex-col p-8 md:min-h-screen">
      <PageHeader
        eyebrow="ABI wound-care billing"
        title="Pipeline"
        description="Run the end-to-end pipeline and watch each stage stream live, from rate-limited PCC ingestion to data characterization."
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

      {/* Top: pipeline progression */}
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
            <Stat
              label="Elapsed"
              value={state.status === "idle" ? "—" : `${elapsed.toFixed(1)}s`}
            />
          </div>
        </CardContent>
      </Card>

      {/* Bottom: visualiser of the actual steps */}
      <Card className="mt-6 flex flex-1 flex-col overflow-hidden">
        <CardHeader>
          <CardTitle className="text-base">Pipeline steps</CardTitle>
          <CardDescription>
            The actual steps as they execute. Extract and route are the next build,
            scoped in ideas.md.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid min-h-0 flex-1 gap-6 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <LiveStepper state={state} />
          </div>
          <div className="flex min-h-[20rem] flex-col overflow-hidden rounded-lg border border-border lg:col-span-2">
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
