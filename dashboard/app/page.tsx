"use client";

import { useEffect, useState, useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type Patient = {
  patient_id: string;
  facility_id: number;
  first_name: string | null;
  last_name: string | null;
  payer_code: string;
  active_wound_dx: boolean;
  wound_type: string | null;
  stage: string | null;
  location: string | null;
  length_cm: number | null;
  width_cm: number | null;
  depth_cm: number | null;
  drainage: string | null;
  data_source: string | null;
  routing: "auto_accept" | "flag_for_review" | "reject";
  reason: string;
  promoted_by_agent: boolean;
};

const ROUTING_STYLES = {
  auto_accept: {
    badge: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    label: "Auto Accept",
  },
  flag_for_review: {
    badge: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    label: "Flag for Review",
  },
  reject: {
    badge: "bg-rose-500/15 text-rose-400 border-rose-500/30",
    label: "Reject",
  },
};

const FACILITY_NAMES: Record<number, string> = {
  101: "Facility A",
  102: "Facility B",
  103: "Facility C",
};

function fmt(v: number | null) {
  return v != null ? v.toFixed(1) : "—";
}

function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: number;
  sub?: string;
  accent?: string;
}) {
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className={`text-3xl font-bold ${accent ?? "text-foreground"}`}>
          {value}
        </p>
        {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
      </CardContent>
    </Card>
  );
}

export default function Dashboard() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [search, setSearch] = useState("");
  const [routingFilter, setRoutingFilter] = useState("all");
  const [facilityFilter, setFacilityFilter] = useState("all");
  const [selected, setSelected] = useState<Patient | null>(null);

  useEffect(() => {
    fetch("/eligibility_data.json")
      .then((r) => r.json())
      .then(setPatients);
  }, []);

  const mcb = useMemo(() => patients.filter((p) => p.payer_code === "MCB"), [patients]);

  const counts = useMemo(
    () => ({
      auto_accept: mcb.filter((p) => p.routing === "auto_accept").length,
      flag_for_review: mcb.filter((p) => p.routing === "flag_for_review").length,
      reject: mcb.filter((p) => p.routing === "reject").length,
    }),
    [mcb]
  );

  const filtered = useMemo(() => {
    return patients.filter((p) => {
      if (routingFilter !== "all" && p.routing !== routingFilter) return false;
      if (facilityFilter !== "all" && String(p.facility_id) !== facilityFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        const name = `${p.first_name ?? ""} ${p.last_name ?? ""}`.toLowerCase();
        if (!p.patient_id.toLowerCase().includes(q) && !name.includes(q)) return false;
      }
      return true;
    });
  }, [patients, routingFilter, facilityFilter, search]);

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border px-6 py-4">
        <h1 className="text-lg font-semibold text-foreground">
          Wound Care Billing — Medicare Part B Eligibility
        </h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          {patients.length} patients across 3 facilities · MCB only shown in summary
        </p>
      </div>

      <div className="px-6 py-6 space-y-6">
        {/* Summary cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            label="MCB Patients"
            value={mcb.length}
            sub="Medicare Part B eligible"
          />
          <StatCard
            label="Auto Accept"
            value={counts.auto_accept}
            sub="Ready to bill"
            accent="text-emerald-400"
          />
          <StatCard
            label="Flag for Review"
            value={counts.flag_for_review}
            sub="Needs clinician review"
            accent="text-amber-400"
          />
          <StatCard
            label="Reject (MCB)"
            value={counts.reject}
            sub="No wound documentation"
            accent="text-rose-400"
          />
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
          <Input
            placeholder="Search patient ID or name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="sm:w-64"
          />
          <Select value={routingFilter} onValueChange={setRoutingFilter}>
            <SelectTrigger className="sm:w-48">
              <SelectValue placeholder="Routing" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All routing</SelectItem>
              <SelectItem value="auto_accept">Auto Accept</SelectItem>
              <SelectItem value="flag_for_review">Flag for Review</SelectItem>
              <SelectItem value="reject">Reject</SelectItem>
            </SelectContent>
          </Select>
          <Select value={facilityFilter} onValueChange={setFacilityFilter}>
            <SelectTrigger className="sm:w-44">
              <SelectValue placeholder="Facility" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All facilities</SelectItem>
              <SelectItem value="101">Facility A (101)</SelectItem>
              <SelectItem value="102">Facility B (102)</SelectItem>
              <SelectItem value="103">Facility C (103)</SelectItem>
            </SelectContent>
          </Select>
          <span className="text-xs text-muted-foreground">
            {filtered.length} patients
          </span>
        </div>

        {/* Table + detail panel */}
        <div className="flex gap-4">
          <div className="flex-1 overflow-auto rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="text-xs">Patient</TableHead>
                  <TableHead className="text-xs">Facility</TableHead>
                  <TableHead className="text-xs">Payer</TableHead>
                  <TableHead className="text-xs">Wound Type</TableHead>
                  <TableHead className="text-xs">Location</TableHead>
                  <TableHead className="text-xs">L × W × D (cm)</TableHead>
                  <TableHead className="text-xs">Drainage</TableHead>
                  <TableHead className="text-xs">Routing</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((p) => {
                  const style = ROUTING_STYLES[p.routing];
                  return (
                    <TableRow
                      key={p.patient_id}
                      className={`cursor-pointer text-xs ${
                        selected?.patient_id === p.patient_id ? "bg-accent" : ""
                      }`}
                      onClick={() =>
                        setSelected(selected?.patient_id === p.patient_id ? null : p)
                      }
                    >
                      <TableCell className="font-mono">
                        <div>{p.patient_id}</div>
                        <div className="text-muted-foreground text-[11px]">
                          {p.first_name} {p.last_name}
                        </div>
                      </TableCell>
                      <TableCell>{FACILITY_NAMES[p.facility_id]}</TableCell>
                      <TableCell>
                        <span
                          className={`text-[11px] font-mono px-1.5 py-0.5 rounded ${
                            p.payer_code === "MCB"
                              ? "bg-primary/15 text-primary"
                              : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {p.payer_code}
                        </span>
                      </TableCell>
                      <TableCell>
                        {p.wound_type ?? (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {p.location ?? (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="font-mono">
                        {fmt(p.length_cm)} × {fmt(p.width_cm)} × {fmt(p.depth_cm)}
                      </TableCell>
                      <TableCell className="capitalize">
                        {p.drainage ?? (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1.5">
                          <Badge
                            variant="outline"
                            className={`text-[11px] ${style.badge}`}
                          >
                            {style.label}
                          </Badge>
                          {p.promoted_by_agent && (
                            <Badge
                              variant="outline"
                              className="text-[10px] bg-violet-500/15 text-violet-400 border-violet-500/30"
                              title="Routing upgraded by AI agent review"
                            >
                              AI
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>

          {/* Detail panel */}
          {selected && (
            <div className="w-80 shrink-0">
              <Card className="sticky top-4">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-sm font-mono">
                        {selected.patient_id}
                      </CardTitle>
                      <p className="text-xs text-muted-foreground">
                        {selected.first_name} {selected.last_name} ·{" "}
                        {FACILITY_NAMES[selected.facility_id]}
                      </p>
                    </div>
                    <Badge
                      variant="outline"
                      className={`text-[11px] ${ROUTING_STYLES[selected.routing].badge}`}
                    >
                      {ROUTING_STYLES[selected.routing].label}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4 text-xs">
                  <div>
                    <p className="text-muted-foreground uppercase tracking-wider text-[10px] mb-1.5">
                      Decision Reason
                    </p>
                    <p className="text-foreground leading-relaxed">{selected.reason}</p>
                  </div>

                  <div>
                    <p className="text-muted-foreground uppercase tracking-wider text-[10px] mb-1.5">
                      Coverage
                    </p>
                    <div className="grid grid-cols-2 gap-1">
                      <span className="text-muted-foreground">Payer</span>
                      <span className="font-mono">{selected.payer_code}</span>
                      <span className="text-muted-foreground">Wound Dx</span>
                      <span>
                        {selected.active_wound_dx ? "Active ICD-10" : "None on record"}
                      </span>
                    </div>
                  </div>

                  <div>
                    <p className="text-muted-foreground uppercase tracking-wider text-[10px] mb-1.5">
                      Wound Details
                    </p>
                    <div className="grid grid-cols-2 gap-1">
                      <span className="text-muted-foreground">Type</span>
                      <span>{selected.wound_type ?? "—"}</span>
                      <span className="text-muted-foreground">Stage</span>
                      <span>{selected.stage ?? "—"}</span>
                      <span className="text-muted-foreground">Location</span>
                      <span>{selected.location ?? "—"}</span>
                      <span className="text-muted-foreground">Length</span>
                      <span className="font-mono">{fmt(selected.length_cm)} cm</span>
                      <span className="text-muted-foreground">Width</span>
                      <span className="font-mono">{fmt(selected.width_cm)} cm</span>
                      <span className="text-muted-foreground">Depth</span>
                      <span className="font-mono">{fmt(selected.depth_cm)} cm</span>
                      <span className="text-muted-foreground">Drainage</span>
                      <span className="capitalize">{selected.drainage ?? "—"}</span>
                    </div>
                  </div>

                  <div>
                    <p className="text-muted-foreground uppercase tracking-wider text-[10px] mb-1">
                      Data Source
                    </p>
                    <span className="font-mono text-muted-foreground">
                      {selected.data_source ?? "—"}
                    </span>
                  </div>

                  {selected.promoted_by_agent && (
                    <div className="rounded-md border border-violet-500/30 bg-violet-500/10 px-3 py-2">
                      <p className="text-[11px] text-violet-400 font-medium">
                        AI Agent Review
                      </p>
                      <p className="text-[11px] text-violet-300/70 mt-0.5 leading-relaxed">
                        Originally flagged for review. Missing fields were extracted from clinical notes by the LLM agent and routing was upgraded to auto accept.
                      </p>
                    </div>
                  )}

                  <button
                    onClick={() => setSelected(null)}
                    className="text-[11px] text-muted-foreground hover:text-foreground transition-colors"
                  >
                    ✕ Close
                  </button>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
