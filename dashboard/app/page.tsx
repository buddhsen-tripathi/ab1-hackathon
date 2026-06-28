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

type AssessmentSection = {
  sectionName: string;
  questions: { question: string; answer: string }[];
};

type Patient = {
  patient_id: string;
  facility_id: number;
  first_name: string | null;
  last_name: string | null;
  payer_code: string;
  mcb_coverage_active: boolean;
  active_wound_dx: boolean;
  wound_type: string | null;
  stage: string | null;
  location: string | null;
  length_cm: number | null;
  width_cm: number | null;
  depth_cm: number | null;
  drainage: string | null;
  data_source: string | null;
  confidence: number | null;
  missing_fields: string | null;
  routing: "auto_accept" | "flag_for_review" | "reject";
  reason: string;
  notes: {
    note_type: string | null;
    effective_date: string | null;
    note_text: string | null;
    created_by: string | null;
  }[];
  assessment: {
    assessment_type: string | null;
    assessment_date: string | null;
    status: string | null;
    sections: AssessmentSection[] | null;
  } | null;
  diagnoses: {
    icd10_code: string | null;
    icd10_description: string | null;
    clinical_status: string | null;
    onset_date: string | null;
  }[];
  coverage: {
    payer_name: string | null;
    payer_code: string | null;
    payer_type: string | null;
    effective_from: string | null;
    effective_to: string | null;
  } | null;
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

type Tab = "all" | "auto_accept" | "flag_for_review" | "reject";

function fmt(v: number | null) {
  return v != null ? v.toFixed(1) : "—";
}

function fmtDate(s: string | null) {
  if (!s) return "—";
  const d = new Date(s);
  return isNaN(d.getTime()) ? s : d.toLocaleDateString();
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

function DetailPanel({
  patient,
  onClose,
}: {
  patient: Patient;
  onClose: () => void;
}) {
  const [noteExpanded, setNoteExpanded] = useState<number | null>(null);

  return (
    <div className="w-96 shrink-0">
      <Card className="sticky top-4 max-h-[calc(100vh-2rem)] flex flex-col">
        <CardHeader className="pb-2 shrink-0">
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="text-sm font-mono">
                {patient.patient_id}
              </CardTitle>
              <p className="text-xs text-muted-foreground">
                {patient.first_name} {patient.last_name} ·{" "}
                {FACILITY_NAMES[patient.facility_id]}
              </p>
            </div>
            <div className="flex flex-col items-end gap-1">
              <Badge
                variant="outline"
                className={`text-[11px] ${ROUTING_STYLES[patient.routing].badge}`}
              >
                {ROUTING_STYLES[patient.routing].label}
              </Badge>
              {patient.confidence != null && (
                <span className="text-[10px] text-muted-foreground font-mono">
                  {(patient.confidence * 100).toFixed(0)}% confidence
                </span>
              )}
            </div>
          </div>
        </CardHeader>

        <CardContent className="overflow-y-auto space-y-5 text-xs pb-4">
          {/* Decision reason */}
          <section>
            <p className="text-muted-foreground uppercase tracking-wider text-[10px] mb-1.5 font-medium">
              Decision Reason
            </p>
            <p className="text-foreground leading-relaxed">{patient.reason}</p>
          </section>

          {/* Coverage */}
          <section>
            <p className="text-muted-foreground uppercase tracking-wider text-[10px] mb-1.5 font-medium">
              Coverage
            </p>
            {patient.coverage ? (
              <div className="grid grid-cols-2 gap-y-1 gap-x-2">
                <span className="text-muted-foreground">Payer</span>
                <span>{patient.coverage.payer_name ?? patient.payer_code}</span>
                <span className="text-muted-foreground">Type</span>
                <span>{patient.coverage.payer_type ?? "—"}</span>
                <span className="text-muted-foreground">Effective</span>
                <span>{fmtDate(patient.coverage.effective_from)}</span>
                {patient.coverage.effective_to && (
                  <>
                    <span className="text-muted-foreground">Expires</span>
                    <span>{fmtDate(patient.coverage.effective_to)}</span>
                  </>
                )}
                <span className="text-muted-foreground">MCB Active</span>
                <span className={patient.mcb_coverage_active ? "text-emerald-400" : "text-rose-400"}>
                  {patient.mcb_coverage_active ? "Yes" : "No"}
                </span>
                <span className="text-muted-foreground">Wound Dx</span>
                <span>{patient.active_wound_dx ? "Active ICD-10" : "None"}</span>
              </div>
            ) : (
              <p className="text-muted-foreground">No coverage data</p>
            )}
          </section>

          {/* Wound Details */}
          <section>
            <p className="text-muted-foreground uppercase tracking-wider text-[10px] mb-1.5 font-medium">
              Wound Details
            </p>
            <div className="grid grid-cols-2 gap-y-1 gap-x-2">
              <span className="text-muted-foreground">Type</span>
              <span className="capitalize">{patient.wound_type ?? "—"}</span>
              <span className="text-muted-foreground">Stage</span>
              <span>{patient.stage ?? "—"}</span>
              <span className="text-muted-foreground">Location</span>
              <span>{patient.location ?? "—"}</span>
              <span className="text-muted-foreground">Length</span>
              <span className="font-mono">{fmt(patient.length_cm)} cm</span>
              <span className="text-muted-foreground">Width</span>
              <span className="font-mono">{fmt(patient.width_cm)} cm</span>
              <span className="text-muted-foreground">Depth</span>
              <span className="font-mono">{fmt(patient.depth_cm)} cm</span>
              <span className="text-muted-foreground">Drainage</span>
              <span className="capitalize">{patient.drainage ?? "—"}</span>
              <span className="text-muted-foreground">Source</span>
              <span className="font-mono text-[10px]">{patient.data_source ?? "—"}</span>
              {patient.confidence != null && (
                <>
                  <span className="text-muted-foreground">Confidence</span>
                  <span className={`font-mono ${
                    patient.confidence >= 0.75 ? "text-emerald-400" :
                    patient.confidence >= 0.40 ? "text-amber-400" : "text-rose-400"
                  }`}>
                    {(patient.confidence * 100).toFixed(0)}%
                  </span>
                </>
              )}
              {patient.missing_fields && (
                <>
                  <span className="text-muted-foreground">Missing</span>
                  <span className="text-amber-400 text-[10px]">
                    {patient.missing_fields.replace(/\|/g, ", ")}
                  </span>
                </>
              )}
            </div>
          </section>

          {/* Diagnoses */}
          {patient.diagnoses.length > 0 && (
            <section>
              <p className="text-muted-foreground uppercase tracking-wider text-[10px] mb-1.5 font-medium">
                Diagnoses ({patient.diagnoses.length})
              </p>
              <div className="space-y-1.5">
                {patient.diagnoses.map((dx, i) => (
                  <div
                    key={i}
                    className="rounded border border-border bg-muted/30 px-2.5 py-1.5"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[11px] text-primary">
                        {dx.icd10_code}
                      </span>
                      <Badge
                        variant="outline"
                        className={`text-[10px] ${
                          dx.clinical_status === "active"
                            ? "border-emerald-500/30 text-emerald-400"
                            : "border-border text-muted-foreground"
                        }`}
                      >
                        {dx.clinical_status}
                      </Badge>
                    </div>
                    <p className="mt-0.5 text-muted-foreground leading-snug">
                      {dx.icd10_description}
                    </p>
                    {dx.onset_date && (
                      <p className="text-[10px] text-muted-foreground/70 mt-0.5">
                        Onset: {fmtDate(dx.onset_date)}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Assessment */}
          {patient.assessment && (
            <section>
              <p className="text-muted-foreground uppercase tracking-wider text-[10px] mb-1.5 font-medium">
                Assessment
              </p>
              <div className="rounded border border-border bg-muted/30 px-2.5 py-2 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-foreground">
                    {patient.assessment.assessment_type}
                  </span>
                  <span className="text-muted-foreground text-[11px]">
                    {fmtDate(patient.assessment.assessment_date)}
                  </span>
                </div>
                {patient.assessment.status && (
                  <Badge
                    variant="outline"
                    className="text-[10px] border-border text-muted-foreground"
                  >
                    {patient.assessment.status}
                  </Badge>
                )}
                {patient.assessment.sections &&
                  patient.assessment.sections.map((sec, i) => (
                    <div key={i}>
                      <p className="text-[10px] uppercase tracking-wider text-muted-foreground/70 mt-1.5 mb-0.5">
                        {sec.sectionName.replace(/_/g, " ")}
                      </p>
                      <div className="grid grid-cols-2 gap-y-0.5 gap-x-2">
                        {sec.questions.map((q, j) => (
                          <>
                            <span key={`q-${j}`} className="text-muted-foreground">
                              {q.question}
                            </span>
                            <span key={`a-${j}`}>{q.answer}</span>
                          </>
                        ))}
                      </div>
                    </div>
                  ))}
              </div>
            </section>
          )}

          {/* Notes */}
          {patient.notes.length > 0 && (
            <section>
              <p className="text-muted-foreground uppercase tracking-wider text-[10px] mb-1.5 font-medium">
                Clinical Notes ({patient.notes.length})
              </p>
              <div className="space-y-2">
                {patient.notes.map((note, i) => (
                  <div
                    key={i}
                    className="rounded border border-border bg-muted/30 px-2.5 py-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-foreground text-[11px]">
                        {note.note_type ?? "Note"}
                      </span>
                      <span className="text-muted-foreground text-[10px]">
                        {fmtDate(note.effective_date)}
                      </span>
                    </div>
                    {note.created_by && (
                      <p className="text-[10px] text-muted-foreground/70 mt-0.5">
                        By: {note.created_by}
                      </p>
                    )}
                    {note.note_text && (
                      <>
                        <p
                          className={`mt-1.5 leading-relaxed text-muted-foreground whitespace-pre-wrap ${
                            noteExpanded === i ? "" : "line-clamp-3"
                          }`}
                        >
                          {note.note_text}
                        </p>
                        <button
                          onClick={() =>
                            setNoteExpanded(noteExpanded === i ? null : i)
                          }
                          className="text-[10px] text-primary mt-1 hover:underline"
                        >
                          {noteExpanded === i ? "Show less" : "Show more"}
                        </button>
                      </>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          <button
            onClick={onClose}
            className="text-[11px] text-muted-foreground hover:text-foreground transition-colors"
          >
            ✕ Close
          </button>
        </CardContent>
      </Card>
    </div>
  );
}

function PatientTable({
  patients,
  selected,
  onSelect,
}: {
  patients: Patient[];
  selected: Patient | null;
  onSelect: (p: Patient | null) => void;
}) {
  return (
    <div className="overflow-auto rounded-lg border border-border">
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
          {patients.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={8}
                className="text-center text-xs text-muted-foreground py-8"
              >
                No patients match the current filters.
              </TableCell>
            </TableRow>
          )}
          {patients.map((p) => {
            const style = ROUTING_STYLES[p.routing];
            return (
              <TableRow
                key={p.patient_id}
                className={`cursor-pointer text-xs ${
                  selected?.patient_id === p.patient_id ? "bg-accent" : ""
                }`}
                onClick={() =>
                  onSelect(selected?.patient_id === p.patient_id ? null : p)
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
                <TableCell className="capitalize">
                  {p.wound_type ?? (
                    <span className="text-muted-foreground normal-case">—</span>
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
                  <div className="flex flex-col gap-0.5">
                    <Badge
                      variant="outline"
                      className={`text-[11px] ${style.badge} w-fit`}
                    >
                      {style.label}
                    </Badge>
                    {p.confidence != null && (
                      <span className={`text-[10px] font-mono ${
                        p.confidence >= 0.75 ? "text-emerald-400/70" :
                        p.confidence >= 0.40 ? "text-amber-400/70" : "text-rose-400/70"
                      }`}>
                        {(p.confidence * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

export default function Dashboard() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [activeTab, setActiveTab] = useState<Tab>("all");
  const [search, setSearch] = useState("");
  const [routingFilter, setRoutingFilter] = useState("all");
  const [facilityFilter, setFacilityFilter] = useState("all");
  const [payerFilter, setPayerFilter] = useState("all");
  const [woundTypeFilter, setWoundTypeFilter] = useState("all");
  const [drainageFilter, setDrainageFilter] = useState("all");
  const [selected, setSelected] = useState<Patient | null>(null);

  useEffect(() => {
    fetch("/eligibility_data.json")
      .then((r) => r.json())
      .then(setPatients);
  }, []);

  const mcb = useMemo(
    () => patients.filter((p) => p.payer_code === "MCB"),
    [patients]
  );

  const counts = useMemo(
    () => ({
      auto_accept: mcb.filter((p) => p.routing === "auto_accept").length,
      flag_for_review: mcb.filter((p) => p.routing === "flag_for_review").length,
      reject: mcb.filter((p) => p.routing === "reject").length,
    }),
    [mcb]
  );

  const woundTypes = useMemo(() => {
    const types = new Set(patients.map((p) => p.wound_type).filter(Boolean));
    return Array.from(types).sort() as string[];
  }, [patients]);

  const drainageTypes = useMemo(() => {
    const types = new Set(patients.map((p) => p.drainage).filter(Boolean));
    return Array.from(types).sort() as string[];
  }, [patients]);

  const payerCodes = useMemo(() => {
    const codes = new Set(patients.map((p) => p.payer_code).filter(Boolean));
    return Array.from(codes).sort() as string[];
  }, [patients]);

  const filtered = useMemo(() => {
    return patients.filter((p) => {
      if (activeTab === "auto_accept" && p.routing !== "auto_accept")
        return false;
      if (activeTab === "flag_for_review" && p.routing !== "flag_for_review")
        return false;
      if (activeTab === "reject" && p.routing !== "reject") return false;
      if (
        activeTab === "all" &&
        routingFilter !== "all" &&
        p.routing !== routingFilter
      )
        return false;
      if (
        facilityFilter !== "all" &&
        String(p.facility_id) !== facilityFilter
      )
        return false;
      if (payerFilter !== "all" && p.payer_code !== payerFilter) return false;
      if (woundTypeFilter !== "all" && p.wound_type !== woundTypeFilter)
        return false;
      if (drainageFilter !== "all" && p.drainage !== drainageFilter)
        return false;
      if (search) {
        const q = search.toLowerCase();
        const name = `${p.first_name ?? ""} ${p.last_name ?? ""}`.toLowerCase();
        if (!p.patient_id.toLowerCase().includes(q) && !name.includes(q))
          return false;
      }
      return true;
    });
  }, [
    patients,
    activeTab,
    routingFilter,
    facilityFilter,
    payerFilter,
    woundTypeFilter,
    drainageFilter,
    search,
  ]);

  const TABS: { id: Tab; label: string; count?: number }[] = [
    { id: "all", label: "All Patients", count: patients.length },
    {
      id: "auto_accept",
      label: "Auto Accept",
      count: patients.filter((p) => p.routing === "auto_accept").length,
    },
    {
      id: "flag_for_review",
      label: "Flag for Review",
      count: patients.filter((p) => p.routing === "flag_for_review").length,
    },
    {
      id: "reject",
      label: "Rejected",
      count: patients.filter((p) => p.routing === "reject").length,
    },
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border px-6 py-4">
        <h1 className="text-lg font-semibold text-foreground">
          Wound Care Billing — Medicare Part B Eligibility
        </h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          {patients.length} patients across 3 facilities · MCB only shown in
          summary
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

        {/* Tabs */}
        <div className="flex gap-1 border-b border-border">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id);
                setSelected(null);
                if (tab.id !== "all") setRoutingFilter("all");
              }}
              className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab.label}
              {tab.count !== undefined && (
                <span
                  className={`ml-1.5 px-1.5 py-0.5 rounded-full text-[10px] ${
                    activeTab === tab.id
                      ? "bg-primary/15 text-primary"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-3 items-center">
          <Input
            placeholder="Search patient ID or name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-56"
          />
          {activeTab === "all" && (
            <Select value={routingFilter} onValueChange={setRoutingFilter}>
              <SelectTrigger className="w-44">
                <SelectValue placeholder="Routing" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All routing</SelectItem>
                <SelectItem value="auto_accept">Auto Accept</SelectItem>
                <SelectItem value="flag_for_review">Flag for Review</SelectItem>
                <SelectItem value="reject">Reject</SelectItem>
              </SelectContent>
            </Select>
          )}
          <Select value={facilityFilter} onValueChange={setFacilityFilter}>
            <SelectTrigger className="w-44">
              <SelectValue placeholder="Facility" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All facilities</SelectItem>
              <SelectItem value="101">Facility A (101)</SelectItem>
              <SelectItem value="102">Facility B (102)</SelectItem>
              <SelectItem value="103">Facility C (103)</SelectItem>
            </SelectContent>
          </Select>
          <Select value={payerFilter} onValueChange={setPayerFilter}>
            <SelectTrigger className="w-36">
              <SelectValue placeholder="Payer" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All payers</SelectItem>
              {payerCodes.map((code) => (
                <SelectItem key={code} value={code}>
                  {code}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={woundTypeFilter} onValueChange={setWoundTypeFilter}>
            <SelectTrigger className="w-44">
              <SelectValue placeholder="Wound type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All wound types</SelectItem>
              {woundTypes.map((wt) => (
                <SelectItem key={wt} value={wt}>
                  {wt}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={drainageFilter} onValueChange={setDrainageFilter}>
            <SelectTrigger className="w-36">
              <SelectValue placeholder="Drainage" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All drainage</SelectItem>
              {drainageTypes.map((dt) => (
                <SelectItem key={dt} value={dt} className="capitalize">
                  {dt}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <span className="text-xs text-muted-foreground">
            {filtered.length} patient{filtered.length !== 1 ? "s" : ""}
          </span>
        </div>

        {/* Table + detail panel */}
        <div className="flex gap-4">
          <div className="flex-1 min-w-0">
            <PatientTable
              patients={filtered}
              selected={selected}
              onSelect={setSelected}
            />
          </div>
          {selected && (
            <DetailPanel patient={selected} onClose={() => setSelected(null)} />
          )}
        </div>
      </div>
    </div>
  );
}
