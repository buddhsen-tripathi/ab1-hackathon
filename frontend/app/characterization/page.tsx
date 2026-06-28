"use client";

import * as React from "react";
import {
  ArrowsClockwise,
  FileText,
  Ruler,
  ShieldWarning,
  Drop,
  WarningDiamond,
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
import { LoadBoundary } from "@/components/ui/load-boundary";
import { PageHeader } from "@/components/ui/page-header";
import { StatusPill } from "@/components/ui/status-pill";
import type { MeasurementDims } from "@/lib/types";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { num, titleize } from "@/lib/utils";

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

export default function CharacterizationPage() {
  const { data, loading, error, reload } = useFetch(() => api.stats());
  const rep = data?.data;

  return (
    <div className="p-8">
      <PageHeader
        eyebrow="Stage 3"
        title="Characterization"
        description="Profile the ingested data before extraction. What formats do notes arrive in, where are measurements complete, and which dirty-data traps need defensive handling?"
        actions={
          <Button variant="outline" size="sm" onClick={reload} disabled={loading}>
            <ArrowsClockwise className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            Refresh
          </Button>
        }
      />

      <LoadBoundary loading={loading} error={error} onRetry={reload}>
        {rep && (
          <div className="space-y-6">
            {/* Payer + coverage */}
            <div className="grid gap-6 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Payer mix</CardTitle>
                  <CardDescription>
                    Primary payer across all {num(rep.patients.total)} patients. Only
                    Medicare Part B (MCB) is billable for wound care.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <BarList data={toBars(rep.patients.primary_payer_mix)} format={num} />
                  <div className="flex items-center justify-between rounded-md bg-muted/40 p-4">
                    <span className="text-sm text-muted-foreground">
                      Billable population (MCB)
                    </span>
                    <span className="font-mono text-sm font-semibold text-foreground">
                      {num(rep.patients.billable_MCB)} ({rep.patients.billable_MCB_pct}%)
                    </span>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Coverage signal</CardTitle>
                  <CardDescription>
                    Confirming active Part B is harder than it looks.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between rounded-md bg-muted/40 p-4">
                    <span className="text-sm text-muted-foreground">
                      Patients with active MCB
                    </span>
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

            {/* Notes */}
            <Card>
              <CardHeader>
                <CardTitle>Progress notes</CardTitle>
                <CardDescription>
                  {num(rep.notes.total)} current notes. Format drives how reliably we
                  can extract wound fields.
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

            {/* Assessments */}
            <Card>
              <CardHeader>
                <CardTitle>Structured assessments</CardTitle>
                <CardDescription>
                  {num(rep.assessments.total)} assessments. Mostly structured JSON, but
                  some pack details into a narrative blob.
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

            {/* Samples */}
            <Card>
              <CardHeader>
                <CardTitle>Note samples by format</CardTitle>
                <CardDescription>
                  One representative note per detected format. This is the raw text the
                  extractor must handle.
                </CardDescription>
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
          </div>
        )}
      </LoadBoundary>
    </div>
  );
}
