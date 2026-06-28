import * as React from "react";
import { cn } from "@/lib/utils";

// The one sanctioned color exception: record state mapped to meaning.
type Bucket = "positive" | "caution" | "progress" | "error" | "neutral";

const BUCKETS: Record<Bucket, { pill: string; dot: string }> = {
  positive: {
    pill: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400",
    dot: "bg-emerald-500",
  },
  caution: {
    pill: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400",
    dot: "bg-amber-500",
  },
  progress: {
    pill: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-400",
    dot: "bg-sky-500",
  },
  error: {
    pill: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-400",
    dot: "bg-red-500",
  },
  neutral: {
    pill: "bg-zinc-100 text-zinc-600 dark:bg-zinc-500/15 dark:text-zinc-400",
    dot: "bg-zinc-400",
  },
};

const KEYWORDS: Record<string, Bucket> = {
  complete: "positive",
  completed: "positive",
  done: "positive",
  verified: "positive",
  active: "positive",
  live: "positive",
  ok: "positive",
  healthy: "positive",
  online: "positive",
  eligible: "positive",
  accept: "positive",
  auto_accept: "positive",
  pending: "caution",
  planned: "caution",
  waiting: "caution",
  paused: "caution",
  review: "caution",
  flag: "caution",
  flag_for_review: "caution",
  partial: "caution",
  running: "progress",
  in_progress: "progress",
  "in-progress": "progress",
  ingesting: "progress",
  processing: "progress",
  sending: "progress",
  failed: "error",
  error: "error",
  reject: "error",
  rejected: "error",
  invalid: "error",
  offline: "error",
  down: "error",
  draft: "neutral",
  archived: "neutral",
  inactive: "neutral",
  idle: "neutral",
  neutral: "neutral",
  ineligible: "neutral",
  skipped: "neutral",
};

function bucketFor(status: string): Bucket {
  return KEYWORDS[status.toLowerCase().replace(/\s+/g, "_")] ?? "neutral";
}

export interface StatusPillProps {
  status: string;
  label?: string;
  className?: string;
}

export function StatusPill({ status, label, className }: StatusPillProps) {
  const b = BUCKETS[bucketFor(status)];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium capitalize",
        b.pill,
        className,
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", b.dot)} />
      {label ?? status.replace(/_/g, " ")}
    </span>
  );
}
