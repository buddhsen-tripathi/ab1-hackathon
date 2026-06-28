"use client";

import * as React from "react";
import {
  ChartBar,
  CircleNotch,
  CloudArrowDown,
  Database,
  Receipt,
  Stethoscope,
  Users,
  type Icon,
} from "@phosphor-icons/react";
import type { PipelineState } from "@/lib/use-pipeline";
import { cn } from "@/lib/utils";

interface Node {
  key: string;
  label: string;
  icon: Icon;
  planned?: boolean;
}

const NODES: Node[] = [
  { key: "roster", label: "Rosters", icon: Users },
  { key: "records", label: "Records", icon: CloudArrowDown },
  { key: "store", label: "Store", icon: Database },
  { key: "characterize", label: "Characterize", icon: ChartBar },
  { key: "extract", label: "Extract", icon: Stethoscope },
  { key: "route", label: "Route", icon: Receipt },
];

const RUNTIME = ["roster", "records", "store", "characterize", "extract", "route"];

function statusOf(state: PipelineState, key: string, planned?: boolean) {
  if (planned) return "planned";
  const s = state.stages[key];
  if (!s || s.status === "idle") return "idle";
  return s.status === "complete" ? "complete" : "running";
}

function overallProgress(state: PipelineState) {
  if (state.status === "complete") return 1;
  let prog = 0;
  for (const k of RUNTIME) {
    const s = state.stages[k];
    if (s?.status === "complete") prog += 1;
    else if (s?.status === "running") {
      prog += s.total ? (s.done ?? 0) / s.total : 0.5;
    }
  }
  return Math.min(1, prog / RUNTIME.length);
}

export function PipelineProgression({ state }: { state: PipelineState }) {
  const progress = overallProgress(state);

  return (
    <div>
      <div className="no-scrollbar flex items-center gap-1 overflow-x-auto pb-1">
        {NODES.map((node, i) => {
          const status = statusOf(state, node.key, node.planned);
          const done = status === "complete";
          const running = status === "running";
          const Icon = node.icon;
          return (
            <React.Fragment key={node.key}>
              {i > 0 && (
                <div
                  className={cn(
                    "h-px min-w-6 flex-1 transition-colors",
                    done || running ? "bg-primary/40" : "bg-border",
                  )}
                  aria-hidden
                />
              )}
              <div className="flex shrink-0 flex-col items-center gap-1.5">
                <div
                  className={cn(
                    "flex h-9 w-9 items-center justify-center rounded-full border transition-colors",
                    done && "border-primary/20 bg-primary text-primary-foreground",
                    running &&
                      "border-sky-500/40 bg-sky-500/10 text-sky-600 dark:text-sky-400",
                    !done &&
                      !running &&
                      "border-border bg-muted text-muted-foreground",
                    node.planned && "border-dashed",
                  )}
                >
                  {running ? (
                    <CircleNotch className="h-4 w-4 animate-spin" />
                  ) : (
                    <Icon className="h-4 w-4" weight={done ? "fill" : "regular"} />
                  )}
                </div>
                <span
                  className={cn(
                    "whitespace-nowrap text-[11px]",
                    done || running ? "text-foreground" : "text-muted-foreground",
                  )}
                >
                  {node.label}
                </span>
              </div>
            </React.Fragment>
          );
        })}
      </div>

      <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full rounded-full transition-[width] duration-500",
            state.status === "error" ? "bg-destructive" : "bg-primary",
          )}
          style={{ width: `${Math.max(progress * 100, state.status === "idle" ? 0 : 3)}%` }}
        />
      </div>
    </div>
  );
}
