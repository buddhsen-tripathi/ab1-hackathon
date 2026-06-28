import * as React from "react";
import { BarList } from "@/components/ui/bar-list";

type Kpi = { kind: "kpi"; label: string; value: string | number; hint?: string };
type Bar = {
  kind: "bar";
  title: string;
  unit?: string;
  data: { label: string; value: number }[];
};
type Tbl = {
  kind: "table";
  title: string;
  columns: string[];
  rows: (string | number)[][];
};
type Widget = Kpi | Bar | Tbl;

export interface DashboardSpec {
  title?: string;
  widgets: Widget[];
}

interface Extracted {
  text: string;
  spec: DashboardSpec | null;
  building: boolean;
}

/** Split an assistant message into prose + an optional ```dashboard JSON block.
 *  `building` is true while the block is still streaming (no closing fence). */
export function extractDashboard(content: string): Extracted {
  const open = content.indexOf("```dashboard");
  if (open === -1) return { text: content, spec: null, building: false };

  const before = content.slice(0, open).trim();
  const rest = content.slice(open + "```dashboard".length);
  const close = rest.indexOf("```");
  if (close === -1) return { text: before, spec: null, building: true };

  const json = rest.slice(0, close).trim();
  const after = rest.slice(close + 3).trim();
  const text = [before, after].filter(Boolean).join("\n\n");
  return { text, spec: validate(json), building: false };
}

function validate(json: string): DashboardSpec | null {
  let obj: unknown;
  try {
    obj = JSON.parse(json);
  } catch {
    return null;
  }
  if (!obj || typeof obj !== "object") return null;
  const raw = obj as { title?: unknown; widgets?: unknown };
  if (!Array.isArray(raw.widgets)) return null;

  const widgets: Widget[] = [];
  for (const w of raw.widgets) {
    if (!w || typeof w !== "object") continue;
    const k = (w as { kind?: string }).kind;
    if (k === "kpi" && "label" in w && "value" in w) {
      widgets.push(w as Kpi);
    } else if (k === "bar" && Array.isArray((w as Bar).data)) {
      widgets.push(w as Bar);
    } else if (
      k === "table" &&
      Array.isArray((w as Tbl).columns) &&
      Array.isArray((w as Tbl).rows)
    ) {
      widgets.push(w as Tbl);
    }
  }
  if (!widgets.length) return null;
  return { title: typeof raw.title === "string" ? raw.title : undefined, widgets };
}

export function ChatDashboard({ spec }: { spec: DashboardSpec }) {
  const kpis = spec.widgets.filter((w): w is Kpi => w.kind === "kpi");
  const rest = spec.widgets.filter((w) => w.kind !== "kpi");

  return (
    <div className="mt-2 space-y-3 rounded-lg border border-border bg-background/60 p-3">
      {spec.title && (
        <p className="font-serif text-sm font-medium text-foreground">{spec.title}</p>
      )}

      {kpis.length > 0 && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {kpis.map((w, i) => (
            <div key={i} className="rounded-md bg-muted/50 p-2.5">
              <p className="truncate text-[10px] uppercase tracking-wider text-muted-foreground">
                {w.label}
              </p>
              <p className="mt-0.5 font-mono text-base font-semibold tabular-nums text-foreground">
                {w.value}
              </p>
              {w.hint && (
                <p className="truncate text-[10px] text-muted-foreground/70">{w.hint}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {rest.map((w, i) =>
        w.kind === "bar" ? (
          <div key={i} className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground">{w.title}</p>
            <BarList
              data={w.data}
              format={(n) => (w.unit === "%" ? `${n}%` : String(n))}
            />
          </div>
        ) : w.kind === "table" ? (
          <div key={i} className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground">{w.title}</p>
            <div className="overflow-x-auto rounded-md border border-border">
              <table className="w-full border-collapse text-xs">
                <thead className="bg-muted/50">
                  <tr>
                    {w.columns.map((c, j) => (
                      <th
                        key={j}
                        className="px-2 py-1.5 text-left font-medium text-muted-foreground"
                      >
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {w.rows.map((r, ri) => (
                    <tr key={ri} className="border-t border-border">
                      {r.map((cell, ci) => (
                        <td key={ci} className="px-2 py-1.5 font-mono text-foreground">
                          {String(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null,
      )}
    </div>
  );
}
