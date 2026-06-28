"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowRight,
  CircleNotch,
  CloudArrowDown,
  Coins,
  Play,
  Pulse,
  Stop,
  Timer,
  Users,
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
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { EventLog } from "@/components/event-log";
import { LiveStepper } from "@/components/live-stepper";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { usePipeline, useElapsedSeconds } from "@/lib/use-pipeline";
import { cn, num, pct, titleize } from "@/lib/utils";

function StatusBanner({
  status,
  elapsed,
  error,
}: {
  status: string;
  elapsed: number;
  error: string | null;
}) {
  if (status === "idle") return null;
  const map: Record<string, { cls: string; text: React.ReactNode }> = {
    running: {
      cls: "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300",
      text: (
        <>
          <CircleNotch className="h-4 w-4 animate-spin" />
          Pipeline running, streaming events live ({elapsed.toFixed(1)}s)
        </>
      ),
    },
    complete: {
      cls: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
      text: <>Pipeline completed in {elapsed.toFixed(1)}s.</>,
    },
    error: {
      cls: "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-300",
      text: <>{error ?? "Pipeline failed."}</>,
    },
  };
  const m = map[status];
  if (!m) return null;
  return (
    <div
      className={cn(
        "mb-6 flex items-center gap-2 rounded-md border px-4 py-3 text-sm",
        m.cls,
      )}
    >
      {m.text}
    </div>
  );
}

export default function PipelinePage() {
  const { state, run, stop, seed } = usePipeline();
  const baseline = useFetch(() => api.stats());

  React.useEffect(() => {
    if (baseline.data) {
      seed(
        baseline.data.request_stats,
        baseline.data.data,
        baseline.data.data.table_counts,
      );
    }
  }, [baseline.data, seed]);

  const running = state.status === "running";
  const elapsed = useElapsedSeconds(running, state.elapsed);

  const stats = state.stats;
  const report = state.report;
  const counts = state.counts;
  const patients = counts?.patients ?? report?.patients.total ?? 0;
  const traps = report
    ? report.notes.doubled_word_trap + report.assessments.laterality_conflict_trap
    : 0;

  return (
    <div className="p-8">
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

      <StatusBanner status={state.status} elapsed={elapsed} error={state.error} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Patients"
          value={num(patients)}
          hint="Across 3 facilities"
          icon={Users}
        />
        <KpiCard
          label="Observed 429 rate"
          value={stats ? pct(stats.observed_429_rate) : "—"}
          hint={
            stats
              ? `${num(stats.rate_limited_429)} of ${num(stats.total_requests)} calls`
              : "Run to measure"
          }
          icon={Pulse}
        />
        <KpiCard
          label="Calls / success"
          value={stats ? stats.calls_per_success.toFixed(2) : "—"}
          hint="Retry cost per record"
          icon={CloudArrowDown}
        />
        <KpiCard
          label="Elapsed"
          value={
            state.status === "idle" ? "—" : `${elapsed.toFixed(1)}s`
          }
          hint={running ? "Running..." : state.elapsed ? "Last run" : undefined}
          icon={Timer}
        />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>Pipeline stages</CardTitle>
            <CardDescription>
              Four runtime stages stream live. Extract and route are the next build,
              scoped in ideas.md.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <LiveStepper state={state} />
          </CardContent>
        </Card>

        <Card className="flex h-[28rem] flex-col overflow-hidden p-0 lg:col-span-2">
          <EventLog log={state.log} />
        </Card>
      </div>

      {report && (
        <div className="mt-6">
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-1.5">
                  <CardTitle>Data snapshot</CardTitle>
                  <CardDescription>
                    Result of the latest characterization. Full breakdown on the
                    characterization page.
                  </CardDescription>
                </div>
                <Button asChild variant="ghost" size="sm">
                  <Link href="/characterization">
                    View full report
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
        </div>
      )}
    </div>
  );
}
