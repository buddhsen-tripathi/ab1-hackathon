"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface ChipOption<T extends string | number> {
  value: T;
  label: string;
}

interface SegmentChipsProps<T extends string | number> {
  options: ChipOption<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
}

export function SegmentChips<T extends string | number>({
  options,
  value,
  onChange,
  className,
}: SegmentChipsProps<T>) {
  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={String(o.value)}
            type="button"
            onClick={() => onChange(o.value)}
            className={cn(
              "rounded-full px-3 py-1 text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              active
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:text-foreground",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
