import * as React from "react";
import type { DbColumn } from "@/lib/types";
import { cn } from "@/lib/utils";

function Cell({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === "") {
    return <span className="italic text-muted-foreground/40">null</span>;
  }
  if (typeof value === "boolean") {
    return <span>{value ? "true" : "false"}</span>;
  }
  if (typeof value === "object") {
    return <span>{JSON.stringify(value)}</span>;
  }
  return <span>{String(value)}</span>;
}

interface DataGridProps {
  columns: DbColumn[];
  rows: Record<string, unknown>[];
  startIndex?: number;
  className?: string;
}

/** Dense, sticky-header data grid for browsing raw stored records. */
export function DataGrid({ columns, rows, startIndex = 0, className }: DataGridProps) {
  return (
    <div className={cn("overflow-auto", className)}>
      <table className="w-full border-collapse text-xs">
        <thead className="sticky top-0 z-10 bg-muted/70 backdrop-blur-sm">
          <tr>
            <th className="w-10 border-b border-border px-3 py-2 text-left text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              #
            </th>
            {columns.map((c) => (
              <th
                key={c.name}
                title={`${c.name} · ${c.type}`}
                className="whitespace-nowrap border-b border-border px-3 py-2 text-left font-medium text-muted-foreground"
              >
                <span className="text-xs">{c.name}</span>
                <span className="ml-1.5 font-mono text-[10px] text-muted-foreground/50">
                  {c.type}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              className="border-b border-border/50 transition-colors hover:bg-muted/30"
            >
              <td className="px-3 py-1.5 font-mono text-[10px] tabular-nums text-muted-foreground/70">
                {startIndex + i + 1}
              </td>
              {columns.map((c) => {
                const v = row[c.name];
                return (
                  <td
                    key={c.name}
                    title={v == null ? "" : String(v)}
                    className="max-w-[320px] truncate px-3 py-1.5 font-mono text-xs text-foreground"
                  >
                    <Cell value={v} />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
