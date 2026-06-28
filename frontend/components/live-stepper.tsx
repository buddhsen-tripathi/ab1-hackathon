"use client";

import * as React from "react";
import { motion } from "framer-motion";
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
import { StatusPill } from "@/components/ui/status-pill";
import type { PipelineState, StageState } from "@/lib/use-pipeline";
import { cn, num } from "@/lib/utils";

interface StageDef {
  key: string;
  title: string;
  description: string;
  icon: Icon;
  planned?: boolean;
}

const RUNTIME_STAGES: StageDef[] = [
  {
    key: "roster",
    title: "Fetch rosters",
    description: "Pull patient rosters for all three facilities.",
    icon: Users,
  },
  {
    key: "records",
    title: "Fetch records",
    description: "Diagnoses, coverage, notes and assessments per patient, with live 429 retries.",
    icon: CloudArrowDown,
  },
  {
    key: "store",
    title: "Store",
    description: "Bulk write full-fidelity raw JSON to SQLite.",
    icon: Database,
  },
  {
    key: "characterize",
    title: "Characterize",
    description: "Profile note formats, payer signal and dirty-data traps.",
    icon: ChartBar,
  },
];

const PLANNED_STAGES: StageDef[] = [
  {
    key: "extract",
    title: "Extract",
    description: "Wound type, stage, location, measurements and drainage.",
    icon: Stethoscope,
    planned: true,
  },
  {
    key: "route",
    title: "Route",
    description: "Reconcile sources, assign auto-accept / flag / reject with a reason.",
    icon: Receipt,
    planned: true,
  },
];

function statusOf(stage: StageState | undefined, planned?: boolean): string {
  if (planned) return "planned";
  if (!stage || stage.status === "idle") return "idle";
  return stage.status === "complete" ? "complete" : "running";
}

function StageRow({
  def,
  stage,
  last,
  index,
}: {
  def: StageDef;
  stage?: StageState;
  last: boolean;
  index: number;
}) {
  const status = statusOf(stage, def.planned);
  const running = status === "running";
  const done = status === "complete";
  const Icon = def.icon;
  const showBar = !def.planned && stage?.total && (running || done);
  const pct = showBar
    ? Math.min(100, Math.round(((stage?.done ?? 0) / (stage?.total || 1)) * 100))
    : 0;

  return (
    <motion.li
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: index * 0.04 }}
      className="relative flex gap-4 pb-6 last:pb-0"
    >
      {!last && (
        <span
          className={cn(
            "absolute left-[18px] top-10 h-[calc(100%-1.5rem)] w-px",
            done ? "bg-primary/30" : "bg-border",
          )}
          aria-hidden
        />
      )}
      <div
        className={cn(
          "z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border transition-colors",
          done && "border-primary/20 bg-primary text-primary-foreground",
          running && "border-sky-500/30 bg-sky-500/10 text-sky-600 dark:text-sky-400",
          !done && !running && "border-border bg-muted text-muted-foreground",
        )}
      >
        {running ? (
          <CircleNotch className="h-4 w-4 animate-spin" />
        ) : (
          <Icon className="h-4 w-4" weight={done ? "fill" : "regular"} />
        )}
      </div>

      <div className="min-w-0 flex-1 pt-1">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h4 className="font-serif text-base font-medium text-foreground">{def.title}</h4>
          <StatusPill status={status} label={status === "idle" ? "Idle" : undefined} />
          {showBar ? (
            <span className="ml-auto font-mono text-xs tabular-nums text-muted-foreground">
              {num(stage?.done ?? 0)} / {num(stage?.total ?? 0)}
            </span>
          ) : null}
        </div>
        <p className="mt-1 text-sm text-muted-foreground">{def.description}</p>
        {showBar ? (
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-sky-500 transition-[width] duration-300"
              style={{ width: `${pct}%` }}
            />
          </div>
        ) : null}
      </div>
    </motion.li>
  );
}

export function LiveStepper({ state }: { state: PipelineState }) {
  const all = [...RUNTIME_STAGES, ...PLANNED_STAGES];
  return (
    <ol className="relative">
      {all.map((def, i) => (
        <StageRow
          key={def.key}
          def={def}
          stage={state.stages[def.key]}
          last={i === all.length - 1}
          index={i}
        />
      ))}
    </ol>
  );
}
