"use client";

import * as React from "react";
import { motion } from "framer-motion";
import type { Icon } from "@phosphor-icons/react";
import { StatusPill } from "@/components/ui/status-pill";
import { cn } from "@/lib/utils";

export interface PipelineStep {
  title: string;
  description: string;
  status: string; // mapped by StatusPill: complete | live | planned ...
  icon: Icon;
  meta?: string;
}

export function PipelineStepper({ steps }: { steps: PipelineStep[] }) {
  return (
    <ol className="relative">
      {steps.map((step, i) => {
        const Icon = step.icon;
        const last = i === steps.length - 1;
        const done = ["complete", "completed", "done", "live", "active"].includes(
          step.status.toLowerCase(),
        );
        return (
          <motion.li
            key={step.title}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, delay: i * 0.05 }}
            className="relative flex gap-4 pb-6 last:pb-0"
          >
            {!last && (
              <span
                className="absolute left-[18px] top-10 h-[calc(100%-1.5rem)] w-px bg-border"
                aria-hidden
              />
            )}
            <div
              className={cn(
                "z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border",
                done
                  ? "border-primary/20 bg-primary text-primary-foreground"
                  : "border-border bg-muted text-muted-foreground",
              )}
            >
              <Icon className="h-4 w-4" weight={done ? "fill" : "regular"} />
            </div>
            <div className="min-w-0 flex-1 pt-1">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <h4 className="font-serif text-base font-medium text-foreground">
                  {step.title}
                </h4>
                <StatusPill status={step.status} />
              </div>
              <p className="mt-1 text-sm text-muted-foreground">{step.description}</p>
              {step.meta && (
                <p className="mt-1.5 font-mono text-xs text-muted-foreground/80">
                  {step.meta}
                </p>
              )}
            </div>
          </motion.li>
        );
      })}
    </ol>
  );
}
