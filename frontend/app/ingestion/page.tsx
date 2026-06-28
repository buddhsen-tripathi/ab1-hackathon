"use client";

import * as React from "react";
import {
  ArrowsClockwise,
  CheckCircle,
  CloudArrowDown,
  Database,
  Warning,
  XCircle,
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
import { LoadBoundary } from "@/components/ui/load-boundary";
import { PageHeader } from "@/components/ui/page-header";
import { StatusPill } from "@/components/ui/status-pill";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { num, pct, titleize } from "@/lib/utils";

export default function IngestionPage() {
  const { data, loading, error, reload } = useFetch(() => api.stats());
  const [busy, setBusy] = React.useState(false);
  const [msg, setMsg] = React.useState<string | null>(null);

  const runIngest = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.ingest();
      setMsg(
        `${titleize(r.status)}. The pull runs in the background, refresh stats in a few seconds.`,
      );
    } catch (e) {
      setMsg(`Failed to start ingestion: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const rs = data?.request_stats;
  const counts = data?.data.table_counts;

  const retryAfter = rs
    ? Object.entries(rs.retry_after_distribution)
        .filter(([k]) => k !== "None")
        .sort((a, b) => Number(a[0]) - Number(b[0]))
        .map(([k, v]) => ({ label: `${k}s`, value: v }))
    : [];

  const countBars = counts
    ? Object.entries(counts).map(([k, v]) => ({ label: titleize(k), value: v }))
    : [];

  return (
    <div className="p-8">
      <PageHeader
        eyebrow="Stage 1 and 2"
        title="Ingestion"
        description="Fetch every record from the PCC API and store it in SQLite. The API rejects roughly 30% of calls with HTTP 429, so each request retries independently."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={reload} disabled={loading}>
              <ArrowsClockwise className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
              Refresh
            </Button>
            <Button onClick={runIngest} disabled={busy}>
              <CloudArrowDown
                className={busy ? "h-4 w-4 animate-pulse" : "h-4 w-4"}
              />
              {busy ? "Starting ingestion" : "Run ingestion"}
            </Button>
          </div>
        }
      />

      {msg && (
        <div className="mb-6 flex items-center gap-2 rounded-md border border-border bg-muted/40 px-4 py-3 text-sm text-foreground">
          <CheckCircle className="h-4 w-4 text-muted-foreground" />
          {msg}
        </div>
      )}

      <LoadBoundary loading={loading} error={error} onRetry={reload}>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            label="Total requests"
            value={rs ? num(rs.total_requests) : "0"}
            hint="All attempts this server session"
            icon={CloudArrowDown}
          />
          <KpiCard
            label="Delivered (200)"
            value={rs ? num(rs.ok) : "0"}
            hint="Successful responses"
            icon={CheckCircle}
          />
          <KpiCard
            label="Rate limited (429)"
            value={rs ? num(rs.rate_limited_429) : "0"}
            hint={rs ? `${pct(rs.observed_429_rate)} observed rate` : undefined}
            icon={Warning}
          />
          <KpiCard
            label="Calls / success"
            value={rs ? rs.calls_per_success.toFixed(3) : "—"}
            hint="Retry overhead per record"
            icon={XCircle}
          />
        </div>

        <div className="mt-8 grid gap-6 lg:grid-cols-3">
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
              <p className="text-sm text-muted-foreground">
                The client fans out one task per (endpoint, patient) across a worker
                pool and retries each item up to 12 times. Because the 429 is random
                rather than a congestion signal, near-immediate retry is valid and
                collapses the back-off tail to roughly zero.
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
              <CardDescription>
                Distribution of server-provided back-off hints (seconds).
              </CardDescription>
            </CardHeader>
            <CardContent>
              {retryAfter.length ? (
                <BarList data={retryAfter} format={(n) => num(n)} />
              ) : (
                <p className="text-sm text-muted-foreground">
                  No 429s recorded yet this session.
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Stored records</CardTitle>
              <CardDescription>
                Row counts per table in the local SQLite store.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-6 md:grid-cols-2">
              <BarList data={countBars} format={(n) => num(n)} />
              <div className="flex items-center gap-3 rounded-md bg-muted/40 p-4">
                <Database className="h-5 w-5 shrink-0 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  Full raw JSON is kept per row so nothing is lost. Promoted columns
                  (ids, payer code, note type) make characterization queries fast.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </LoadBoundary>
    </div>
  );
}
