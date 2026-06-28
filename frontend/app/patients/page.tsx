"use client";

import * as React from "react";
import { ArrowsClockwise, MagnifyingGlass, Users } from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { LoadBoundary } from "@/components/ui/load-boundary";
import { PageHeader } from "@/components/ui/page-header";
import { SegmentChips } from "@/components/ui/segment-chips";
import { StatusPill } from "@/components/ui/status-pill";
import type { Patient } from "@/lib/types";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { num } from "@/lib/utils";

const FACILITY_OPTIONS = [
  { value: 0, label: "All facilities" },
  { value: 101, label: "Facility A" },
  { value: 102, label: "Facility B" },
  { value: 103, label: "Facility C" },
];

const PAYER_LABEL: Record<string, string> = {
  MCB: "Medicare Part B",
  MCA: "Medicare Part A",
  MCD: "Medicaid",
  HMO: "HMO",
};

function fullName(p: Patient) {
  return [p.first_name, p.last_name].filter(Boolean).join(" ") || "—";
}

export default function PatientsPage() {
  const { data, loading, error, reload } = useFetch(() => api.patients());
  const [facility, setFacility] = React.useState(0);
  const [query, setQuery] = React.useState("");

  const rows = React.useMemo(() => {
    let r = data ?? [];
    if (facility) r = r.filter((p) => p.facility_id === facility);
    const q = query.trim().toLowerCase();
    if (q) {
      r = r.filter(
        (p) =>
          p.patient_id.toLowerCase().includes(q) ||
          fullName(p).toLowerCase().includes(q),
      );
    }
    return r;
  }, [data, facility, query]);

  const columns: Column<Patient>[] = [
    {
      key: "patient_id",
      header: "PCC ID",
      className: "font-mono text-xs",
      render: (p) => p.patient_id,
    },
    { key: "name", header: "Name", render: (p) => fullName(p) },
    {
      key: "facility_id",
      header: "Facility",
      className: "font-mono text-xs text-muted-foreground",
      render: (p) => p.facility_id,
    },
    {
      key: "gender",
      header: "Gender",
      className: "text-muted-foreground",
      render: (p) => p.gender ?? "—",
    },
    {
      key: "payer",
      header: "Primary payer",
      render: (p) => (
        <Badge variant="muted">
          {p.primary_payer_code
            ? PAYER_LABEL[p.primary_payer_code] ?? p.primary_payer_code
            : "Unknown"}
        </Badge>
      ),
    },
    {
      key: "eligible",
      header: "Billing eligibility",
      render: (p) =>
        p.primary_payer_code === "MCB" ? (
          <StatusPill status="eligible" label="Eligible" />
        ) : (
          <StatusPill status="ineligible" label="Not eligible" />
        ),
    },
    {
      key: "admission",
      header: "Admission",
      render: (p) =>
        p.is_new_admission ? <Badge variant="soon">New</Badge> : null,
    },
  ];

  const eligibleCount = rows.filter((p) => p.primary_payer_code === "MCB").length;

  return (
    <div className="p-8">
      <PageHeader
        eyebrow="Roster"
        title="Patients"
        description="Every ingested patient across the three facilities. Medicare Part B patients are the billable target population for wound care."
        actions={
          <Button variant="outline" size="sm" onClick={reload} disabled={loading}>
            <ArrowsClockwise className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            Refresh
          </Button>
        }
      />

      <LoadBoundary loading={loading} error={error} onRetry={reload}>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <SegmentChips
            options={FACILITY_OPTIONS}
            value={facility}
            onChange={setFacility}
          />
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground">
              {num(rows.length)} shown · {num(eligibleCount)} MCB-eligible
            </span>
            <div className="relative w-56">
              <MagnifyingGlass className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search name or ID"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="pl-8"
              />
            </div>
          </div>
        </div>

        {rows.length ? (
          <DataTable
            columns={columns}
            data={rows}
            rowKey={(p) => p.id}
          />
        ) : (
          <Card>
            <EmptyState
              icon={Users}
              title="No patients match"
              description="Try a different facility filter or clear the search. If the roster is empty, run ingestion first."
            />
          </Card>
        )}
      </LoadBoundary>
    </div>
  );
}
