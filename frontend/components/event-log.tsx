"use client";

import * as React from "react";
import { Terminal } from "@phosphor-icons/react";
import type { LogEntry } from "@/lib/use-pipeline";
import { cn } from "@/lib/utils";

function toneFor(type: string): string {
  if (type === "error") return "text-red-600 dark:text-red-400";
  if (type === "pipeline_complete") return "text-emerald-600 dark:text-emerald-400";
  if (type === "stage_complete") return "text-foreground";
  if (type === "stage_start" || type === "pipeline_start")
    return "text-sky-600 dark:text-sky-400";
  return "text-muted-foreground";
}

export function EventLog({ log, className }: { log: LogEntry[]; className?: string }) {
  const endRef = React.useRef<HTMLDivElement>(null);
  const lastText = log[log.length - 1]?.text;

  React.useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [log.length, lastText]);

  return (
    <div className={cn("flex h-full flex-col", className)}>
      <div className="flex items-center gap-2 border-b border-border px-4 py-2.5">
        <Terminal className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Event stream
        </span>
        <span className="ml-auto font-mono text-[11px] text-muted-foreground/70">
          {log.length} events
        </span>
      </div>
      <div className="no-scrollbar min-h-0 flex-1 overflow-y-auto p-4">
        {log.length === 0 ? (
          <p className="font-mono text-xs text-muted-foreground/60">
            Run the pipeline to stream events here.
          </p>
        ) : (
          <div className="space-y-0.5">
            {log.map((e) => (
              <pre
                key={e.id}
                className={cn(
                  "whitespace-pre-wrap break-words font-mono text-xs leading-relaxed",
                  toneFor(e.type),
                )}
              >
                {e.text}
              </pre>
            ))}
            <div ref={endRef} />
          </div>
        )}
      </div>
    </div>
  );
}
