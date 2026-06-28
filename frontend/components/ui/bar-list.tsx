import * as React from "react";
import { cn } from "@/lib/utils";

export interface BarItem {
  label: string;
  value: number;
  hint?: string;
}

interface BarListProps {
  data: BarItem[];
  format?: (n: number) => React.ReactNode;
  className?: string;
}

export function BarList({ data, format, className }: BarListProps) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className={cn("space-y-3", className)}>
      {data.map((d) => (
        <div key={d.label} className="space-y-1.5">
          <div className="flex items-baseline justify-between gap-3 text-xs">
            <span className="truncate text-foreground">{d.label}</span>
            <span className="shrink-0 font-mono tabular-nums text-muted-foreground">
              {format ? format(d.value) : d.value}
            </span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-[width] duration-500"
              style={{ width: `${Math.max((d.value / max) * 100, 2)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
