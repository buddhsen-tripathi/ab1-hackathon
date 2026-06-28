import { useState } from "react";
import { api } from "../api";
import { HELP, missingFieldHelp } from "../help";
import type { Meta, Patient, PatientDetail, RoutingDecision } from "../types";
import { InfoTip } from "./InfoTip";

const COLUMN_CONFIG: Record<
  RoutingDecision,
  { label: string; color: string; bg: string; tip: string }
> = {
  auto_accept: { label: "Ready to Bill", color: "#059669", bg: "#ecfdf5", tip: HELP.ready_to_bill },
  flag_for_review: { label: "Needs Review", color: "#b45309", bg: "#fffbeb", tip: HELP.needs_review },
  reject: { label: "Do Not Route", color: "#b91c1c", bg: "#fef2f2", tip: HELP.do_not_route },
};

function woundSummary(p: Patient): string {
  const parts: string[] = [];
  if (p.wound_type) parts.push(p.stage ? `${p.wound_type}, stage ${p.stage}` : p.wound_type);
  if (p.location) parts.push(p.location);
  const dims = [p.length_cm, p.width_cm, p.depth_cm].filter(Boolean);
  if (dims.length) parts.push(`${dims.join(" × ")} cm`);
  if (p.drainage_amount) parts.push(`${p.drainage_amount} drainage`);
  return parts.join(" · ") || "No wound data extracted";
}

function llmSuggestionBadge(check: string | null | undefined): { label: string; className: string } | null {
  if (!check || check === "skipped") return null;
  if (check === "billable") {
    return { label: "AI: likely billable", className: "bg-violet-100 text-violet-800 border-violet-200" };
  }
  if (check === "needs_documentation") {
    return { label: "AI: needs documentation", className: "bg-violet-50 text-violet-900 border-violet-200" };
  }
  return { label: "AI suggestion", className: "bg-violet-50 text-violet-800 border-violet-200" };
}

function PatientCard({
  patient,
  meta,
}: {
  patient: Patient;
  meta: Meta | null;
}) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<PatientDetail | null>(null);
  const [loading, setLoading] = useState(false);

  const labels = meta?.field_labels ?? {};
  const eligible = patient.submission_eligible || patient.has_active_mcb;
  const llmBadge = llmSuggestionBadge(patient.llm_check);

  const toggle = async () => {
    if (!open && !detail) {
      setLoading(true);
      try {
        setDetail(await api.patient(patient.patient_id));
      } finally {
        setLoading(false);
      }
    }
    setOpen(!open);
  };

  return (
    <div className="bg-surface border border-border rounded-lg mb-2 overflow-hidden">
      <button
        type="button"
        onClick={toggle}
        className="w-full text-left px-3 py-2.5 hover:bg-slate-50 transition-colors"
      >
        <div className="flex justify-between items-start gap-2">
          <div>
            <div className="font-semibold text-sm">{patient.patient_id}</div>
            <div className="text-xs text-muted">
              {patient.first_name} {patient.last_name}
              {patient.is_new_admission && (
                <span className="ml-1 inline-flex items-center gap-0.5 text-blue-700 font-bold">
                  NEW
                  <InfoTip text={HELP.new_admission} className="font-normal" />
                </span>
              )}
            </div>
          </div>
          <span className="text-muted text-xs">{open ? "▲" : "▼"}</span>
        </div>
        <div className="mt-1.5 flex flex-wrap gap-1 items-center">
          <span
            className={`inline-flex items-center gap-0.5 text-[0.65rem] font-bold uppercase px-1.5 py-0.5 rounded ${
              eligible ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
            }`}
          >
            {eligible ? "Part B eligible" : "Not Part B"}
            <InfoTip text={eligible ? HELP.part_b_eligible : HELP.not_part_b} />
          </span>
          {patient.missing_fields.slice(0, 3).map((f) => (
            <span
              key={f}
              className="inline-flex items-center gap-0.5 text-[0.65rem] font-medium px-1.5 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200"
            >
              Missing {labels[f] ?? f}
              <InfoTip text={missingFieldHelp(f)} />
            </span>
          ))}
          {patient.missing_fields.length > 3 && (
            <span className="text-[0.65rem] text-muted">+{patient.missing_fields.length - 3}</span>
          )}
          {llmBadge && (
            <span
              className={`inline-flex items-center gap-0.5 text-[0.65rem] font-medium px-1.5 py-0.5 rounded border ${llmBadge.className}`}
            >
              {llmBadge.label}
              <InfoTip text={HELP.llm_suggestions} />
            </span>
          )}
        </div>
        {patient.llm_check_note && patient.llm_check !== "skipped" && (
          <p className="text-[0.65rem] text-violet-800 mt-1.5 line-clamp-2 italic">
            {patient.llm_check_note}
          </p>
        )}
        <p className="text-xs mt-2 text-slate-700 line-clamp-2">{woundSummary(patient)}</p>
        <p className="text-[0.65rem] text-muted mt-1 inline-flex items-center gap-1 flex-wrap">
          <span>
            {patient.facility_name ?? patient.facility_id} ·{" "}
            {(patient.extraction_confidence * 100).toFixed(0)}% confidence
          </span>
          <InfoTip text={HELP.confidence} />
        </p>
      </button>

      {open && (
        <div className="border-t border-border px-3 py-3 bg-slate-50/50 text-sm">
          {loading && <p className="text-muted text-xs">Loading chart…</p>}
          <p className="text-xs text-slate-600 mb-3">{patient.reason}</p>
          {patient.llm_check && patient.llm_check !== "skipped" && (
            <div className="text-xs mb-3 text-violet-800 bg-violet-50 border border-violet-200 rounded px-2 py-1.5">
              <span className="font-medium inline-flex items-center gap-1">
                AI suggestion
                <InfoTip text={HELP.llm_suggestions} />
              </span>
              <p className="mt-1">{patient.llm_check_note}</p>
            </div>
          )}
          <div className="grid grid-cols-2 gap-2 mb-3 text-xs">
            <div><span className="text-muted">Type:</span> {patient.wound_type ?? "—"}</div>
            <div><span className="text-muted">Stage:</span> {patient.stage ?? "—"}</div>
            <div><span className="text-muted">Location:</span> {patient.location ?? "—"}</div>
            <div>
              <span className="text-muted">Size:</span>{" "}
              {[patient.length_cm, patient.width_cm, patient.depth_cm].filter(Boolean).join(" × ") || "—"}
              {[patient.length_cm, patient.width_cm, patient.depth_cm].some(Boolean) ? " cm" : ""}
            </div>
            <div><span className="text-muted">Drainage:</span> {patient.drainage_amount ?? "—"}</div>
            <div><span className="text-muted">Source:</span> {patient.extraction_source}</div>
          </div>
          {detail?.note_html && (
            <div>
              <p className="text-xs font-medium text-muted mb-1">Clinical note (highlights = extracted)</p>
              <div
                className="text-xs bg-white border border-border rounded p-3 max-h-40 overflow-y-auto leading-relaxed"
                dangerouslySetInnerHTML={{ __html: detail.note_html }}
              />
            </div>
          )}
          {detail?.coverage && detail.coverage.length > 0 && (
            <div className="mt-2 text-xs">
              <span className="font-medium text-muted">Coverage: </span>
              {detail.coverage.map((c: Record<string, unknown>, i) => (
                <span key={i}>
                  {String(c.payer_name)} ({String(c.payer_code)})
                  {!c.effective_to ? " active" : ""}
                  {i < detail.coverage!.length - 1 ? " · " : ""}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function KanbanColumn({
  decision,
  patients,
  meta,
}: {
  decision: RoutingDecision;
  patients: Patient[];
  meta: Meta | null;
}) {
  const cfg = COLUMN_CONFIG[decision];

  return (
    <div className="min-w-0 flex-1">
      <div
        className="rounded-lg px-3 py-2.5 mb-3 flex justify-between items-center border border-border"
        style={{ background: cfg.bg, borderLeftWidth: 4, borderLeftColor: cfg.color }}
      >
        <span className="text-xs font-bold uppercase tracking-wide inline-flex items-center gap-1" style={{ color: cfg.color }}>
          {cfg.label}
          <InfoTip text={cfg.tip} />
        </span>
        <span className="text-xs font-semibold bg-white px-2 py-0.5 rounded-full text-muted">
          {patients.length}
        </span>
      </div>
      {patients.length === 0 ? (
        <p className="text-center text-sm text-muted py-8">No patients</p>
      ) : (
        patients.slice(0, 50).map((p) => (
          <PatientCard key={p.patient_id} patient={p} meta={meta} />
        ))
      )}
      {patients.length > 50 && (
        <p className="text-xs text-muted text-center">+ {patients.length - 50} more</p>
      )}
    </div>
  );
}
