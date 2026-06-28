import type { Stats } from "../types";
import { HELP } from "../help";
import { InfoTip } from "./InfoTip";

interface Props {
  stats: Stats | null;
}

const METRICS: { label: string; key: keyof Stats["routing"] | "filtered" | "submission_eligible" | "llm_suggestions"; tip: string }[] = [
  { label: "Shown", key: "filtered", tip: HELP.shown_metric },
  { label: "Part B eligible", key: "submission_eligible", tip: HELP.part_b_metric },
  { label: "Ready to bill", key: "auto_accept", tip: HELP.ready_metric },
  { label: "Needs review", key: "flag_for_review", tip: HELP.review_metric },
  { label: "Not eligible", key: "reject", tip: HELP.reject_metric },
  { label: "LLM suggestions", key: "llm_suggestions", tip: HELP.llm_suggestions },
];

function metricValue(stats: Stats, key: string): number {
  if (key === "filtered") return stats.filtered;
  if (key === "submission_eligible") return stats.submission_eligible;
  if (key === "llm_suggestions") return stats.llm_suggestions;
  return stats.routing[key as keyof Stats["routing"]] ?? 0;
}

export function Metrics({ stats }: Props) {
  if (!stats) return null;

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        {METRICS.map(({ label, key, tip }) => (
          <div key={label} className="bg-surface border border-border rounded-lg px-4 py-3">
            <div className="text-[0.7rem] font-semibold uppercase tracking-wide text-muted inline-flex items-center gap-1">
              {label}
              <InfoTip text={tip} />
            </div>
            <div className="text-2xl font-bold mt-1">{metricValue(stats, key)}</div>
          </div>
        ))}
    </div>
  );
}
