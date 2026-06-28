"use client";

import * as React from "react";
import { ArrowsClockwise, ClipboardText, MagnifyingGlass } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { LoadBoundary } from "@/components/ui/load-boundary";
import { PageHeader } from "@/components/ui/page-header";
import { StatusPill } from "@/components/ui/status-pill";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import type { EligibilityResult } from "@/lib/types";
import { cn, num, titleize } from "@/lib/utils";

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-full px-3 py-1 text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active
          ? "bg-primary text-primary-foreground"
          : "bg-muted text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

function FilterRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="mr-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      {children}
    </div>
  );
}

const DECISIONS = ["auto_accept", "flag_for_review", "reject"];
const MISSING = ["depth_cm", "wound_type", "drainage_amount"];

function dims(r: EligibilityResult) {
  if (r.length_cm == null && r.width_cm == null && r.depth_cm == null) return "—";
  return [r.length_cm, r.width_cm, r.depth_cm].map((x) => x ?? "—").join(" × ");
}

export default function WorklistPage() {
  const { data, loading, error, reload } = useFetch(() => api.eligibility());

  const [search, setSearch] = React.useState("");
  const [decision, setDecision] = React.useState<string | null>(null);
  const [facility, setFacility] = React.useState<number | null>(null);
  const [eligibleOnly, setEligibleOnly] = React.useState(false);
  const [newAdmOnly, setNewAdmOnly] = React.useState(false);
  const [missing, setMissing] = React.useState<string | null>(null);

  const all = data ?? [];
  const rows = React.useMemo(() => {
    const q = search.trim().toLowerCase();
    return all.filter((r) => {
      if (decision && r.routing_decision !== decision) return false;
      if (facility != null && r.facility_id !== facility) return false;
      if (eligibleOnly && !r.has_active_mcb) return false;
      if (newAdmOnly && !r.is_new_admission) return false;
      if (missing && !(r.missing_fields ?? []).includes(missing)) return false;
      if (q) {
        const hay = `${r.patient_id} ${r.first_name ?? ""} ${r.last_name ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [all, search, decision, facility, eligibleOnly, newAdmOnly, missing]);

  const columns: Column<EligibilityResult>[] = [
    {
      key: "patient",
      header: "Patient",
      render: (r) => (
        <div>
          <div className="font-mono text-xs text-foreground">{r.patient_id}</div>
          <div className="text-xs text-muted-foreground">
            {[r.first_name, r.last_name].filter(Boolean).join(" ") || "—"}
          </div>
        </div>
      ),
    },
    { key: "facility_id", header: "Facility" },
    {
      key: "decision",
      header: "Decision",
      render: (r) => <StatusPill status={r.routing_decision} />,
    },
    {
      key: "wound",
      header: "Wound",
      render: (r) =>
        r.wound_type
          ? titleize(r.wound_type) + (r.stage ? ` (stage ${r.stage})` : "")
          : "—",
    },
    { key: "size", header: "L × W × D (cm)", render: dims },
    { key: "drainage_amount", header: "Drainage", render: (r) => r.drainage_amount ?? "—" },
    {
      key: "conf",
      header: "Conf.",
      render: (r) =>
        r.extraction_confidence ? `${Math.round(r.extraction_confidence * 100)}%` : "—",
    },
    {
      key: "reason",
      header: "Reason",
      className: "max-w-md",
      render: (r) => (
        <span className="line-clamp-2 text-xs text-muted-foreground">{r.reason}</span>
      ),
    },
  ];

  return (
    <div className="p-8">
      <PageHeader
        eyebrow="Billing worklist"
        title="Worklist"
        description="Every patient with a routing decision and a plain-English reason. Filter to the cases a biller should act on."
        actions={
          <Button variant="outline" size="sm" onClick={reload} disabled={loading}>
            <ArrowsClockwise className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            Refresh
          </Button>
        }
      />

      <LoadBoundary loading={loading} error={error} onRetry={reload}>
        <div className="space-y-4">
          {/* Filters */}
          <div className="space-y-3 rounded-lg border border-border bg-muted/20 p-4">
            <div className="relative w-full max-w-xs">
              <MagnifyingGlass className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search patient ID or name…"
                className="pl-8"
              />
            </div>
            <FilterRow label="Decision">
              <Chip active={decision === null} onClick={() => setDecision(null)}>All</Chip>
              {DECISIONS.map((d) => (
                <Chip key={d} active={decision === d} onClick={() => setDecision(d)}>
                  {titleize(d)}
                </Chip>
              ))}
            </FilterRow>
            <FilterRow label="Facility">
              <Chip active={facility === null} onClick={() => setFacility(null)}>All</Chip>
              {[101, 102, 103].map((f) => (
                <Chip key={f} active={facility === f} onClick={() => setFacility(f)}>
                  {f}
                </Chip>
              ))}
            </FilterRow>
            <FilterRow label="Missing">
              <Chip active={missing === null} onClick={() => setMissing(null)}>Any</Chip>
              {MISSING.map((m) => (
                <Chip key={m} active={missing === m} onClick={() => setMissing(m)}>
                  {titleize(m.replace(/_cm$/, ""))}
                </Chip>
              ))}
            </FilterRow>
            <FilterRow label="Flags">
              <Chip active={eligibleOnly} onClick={() => setEligibleOnly((v) => !v)}>
                Billable (MCB) only
              </Chip>
              <Chip active={newAdmOnly} onClick={() => setNewAdmOnly((v) => !v)}>
                New admissions only
              </Chip>
            </FilterRow>
          </div>

          <p className="text-xs text-muted-foreground">
            Showing <span className="font-mono text-foreground">{num(rows.length)}</span> of{" "}
            <span className="font-mono text-foreground">{num(all.length)}</span> patients
          </p>

          {rows.length > 0 ? (
            <DataTable
              columns={columns}
              data={rows}
              rowKey={(r) => r.internal_id}
            />
          ) : (
            <EmptyState
              icon={ClipboardText}
              title="No matching patients"
              description="No patients match these filters. Try clearing some, or run the pipeline if the worklist is empty."
            />
          )}
        </div>
      </LoadBoundary>
    </div>
  );
}
