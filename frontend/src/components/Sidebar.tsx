import type { Meta, Stats } from "../types";
import type { Filters, MissingField, RoutingDecision } from "../types";
import { HELP, missingFieldHelp } from "../help";
import { InfoTip, LabelWithTip } from "./InfoTip";

interface Props {
  filters: Filters;
  meta: Meta | null;
  stats: Stats | null;
  onChange: (patch: Partial<Filters>) => void;
}

const ALL_ROUTING: RoutingDecision[] = ["auto_accept", "flag_for_review", "reject"];

const ISSUE_FIELDS: MissingField[] = [
  "medicare_part_b",
  "wound_documentation",
  "wound_type",
  "length_cm",
  "width_cm",
  "depth_cm",
  "drainage_amount",
];

export function Sidebar({ filters, meta, stats, onChange }: Props) {
  const labels = meta?.field_labels ?? {};

  const toggleMissing = (field: MissingField) => {
    const set = new Set(filters.missingFields);
    if (set.has(field)) set.delete(field);
    else set.add(field);
    onChange({ missingFields: [...set] });
  };

  const toggleRouting = (r: RoutingDecision) => {
    const set = new Set(filters.routing);
    if (set.has(r)) set.delete(r);
    else set.add(r);
    onChange({ routing: [...set] });
  };

  return (
    <aside className="w-72 shrink-0 bg-surface border-r border-border p-4 overflow-y-auto h-screen sticky top-0">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-muted mb-3">Filters</h2>

      <label className="block text-sm font-medium mb-1">Facility</label>
      <select
        className="w-full border border-border rounded-md px-2 py-1.5 text-sm mb-4"
        value={filters.facilityId ?? ""}
        onChange={(e) =>
          onChange({ facilityId: e.target.value ? Number(e.target.value) : null })
        }
      >
        <option value="">All facilities</option>
        {meta?.facilities.map((f) => (
          <option key={f.id} value={f.id}>
            {f.name}
          </option>
        ))}
      </select>

      <LabelWithTip label="Part B submission" tip={HELP.part_b_filter} className="block text-sm font-medium mb-1" />
      <select
        className="w-full border border-border rounded-md px-2 py-1.5 text-sm mb-4"
        value={filters.submissionEligible}
        onChange={(e) =>
          onChange({
            submissionEligible: e.target.value as Filters["submissionEligible"],
          })
        }
      >
        <option value="all">All patients</option>
        <option value="eligible">Part B eligible</option>
        <option value="not_eligible">Not Part B eligible</option>
      </select>

      <LabelWithTip label="Documentation status" tip={HELP.doc_status_filter} className="block text-sm font-medium mb-2" />
      <div className="flex flex-wrap gap-1.5 mb-4">
        {ALL_ROUTING.map((r) => (
          <button
            key={r}
            type="button"
            onClick={() => toggleRouting(r)}
            className={`text-xs px-2 py-1 rounded-full border font-medium ${
              filters.routing.includes(r)
                ? "bg-slate-900 text-white border-slate-900"
                : "bg-white text-muted border-border"
            }`}
          >
            {meta?.routing_labels[r] ?? r}
          </button>
        ))}
      </div>

      <LabelWithTip label="Missing / issues" tip={HELP.missing_filter} className="block text-sm font-medium mb-2" />
      <div className="space-y-1 mb-4 max-h-48 overflow-y-auto">
        {ISSUE_FIELDS.map((field) => {
          const count = stats?.missing_field_counts[field] ?? 0;
          return (
            <label key={field} className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={filters.missingFields.includes(field)}
                onChange={() => toggleMissing(field)}
                className="rounded border-border"
              />
              <span className="flex-1 inline-flex items-center gap-1">
                {labels[field] ?? field}
                <InfoTip text={missingFieldHelp(field)} />
              </span>
              <span className="text-xs text-muted tabular-nums">{count}</span>
            </label>
          );
        })}
      </div>

      <label className="flex items-center gap-2 text-sm mb-4 cursor-pointer">
        <input
          type="checkbox"
          checked={filters.newAdmissionOnly}
          onChange={(e) => onChange({ newAdmissionOnly: e.target.checked })}
          className="rounded border-border"
        />
        <LabelWithTip label="New admissions only" tip={HELP.new_admission_filter} />
      </label>

      <label className="block text-sm font-medium mb-1">Search</label>
      <input
        type="search"
        placeholder="Patient ID or name…"
        className="w-full border border-border rounded-md px-2 py-1.5 text-sm mb-6"
        value={filters.search}
        onChange={(e) => onChange({ search: e.target.value })}
      />

      {meta?.pipeline && (
        <>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted mb-2 mt-4">Last run</h2>
          <p className="text-xs text-muted">
            {String(meta.pipeline.elapsed_seconds ?? "?")}s · {String(meta.pipeline.patients ?? "?")} pts
          </p>
        </>
      )}
    </aside>
  );
}
