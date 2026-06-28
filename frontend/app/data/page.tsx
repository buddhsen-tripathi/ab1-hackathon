"use client";

import * as React from "react";
import {
  ArrowsClockwise,
  CaretLeft,
  CaretRight,
  Table as TableIcon,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DataGrid } from "@/components/data-grid";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadBoundary } from "@/components/ui/load-boundary";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { cn, num, titleize } from "@/lib/utils";

const TABLE_ORDER = ["patients", "diagnoses", "coverage", "notes", "assessments"];
const PAGE_SIZE = 50;

export default function DataPage() {
  const tables = useFetch(() => api.dbTables());
  const [table, setTable] = React.useState("patients");
  const [page, setPage] = React.useState(1);

  const offset = (page - 1) * PAGE_SIZE;
  const data = useFetch(() => api.dbTable(table, PAGE_SIZE, offset), [table, offset]);

  const selectTable = (t: string) => {
    setTable(t);
    setPage(1);
  };

  const total = data.data?.total ?? 0;
  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);

  const counts = tables.data ?? {};
  const tabList = TABLE_ORDER.filter((t) => t in counts).length
    ? TABLE_ORDER.filter((t) => t in counts)
    : TABLE_ORDER;

  return (
    <div className="p-8">
      <PageHeader
        eyebrow="Stored records"
        title="Data"
        description="Browse the raw records ingested into each table. This is the original PCC data as stored, before extraction."
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              tables.reload();
              data.reload();
            }}
            disabled={data.loading}
          >
            <ArrowsClockwise className={data.loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            Refresh
          </Button>
        }
      />

      {/* Table picker */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {tabList.map((t) => {
          const active = t === table;
          return (
            <button
              key={t}
              type="button"
              onClick={() => selectTable(t)}
              className={cn(
                "inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                active
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:text-foreground",
              )}
            >
              {titleize(t)}
              <span
                className={cn(
                  "font-mono text-[10px] tabular-nums",
                  active ? "text-primary-foreground/70" : "text-muted-foreground/60",
                )}
              >
                {counts[t] != null ? num(counts[t]) : "—"}
              </span>
            </button>
          );
        })}
      </div>

      <Card className="overflow-hidden p-0">
        <LoadBoundary
          loading={data.loading && !data.data}
          error={data.error}
          onRetry={data.reload}
          skeleton={
            <div className="space-y-2 p-4">
              {Array.from({ length: 12 }).map((_, i) => (
                <Skeleton key={i} className="h-7 w-full" />
              ))}
            </div>
          }
        >
          {data.data && data.data.rows.length > 0 ? (
            <>
              <DataGrid
                columns={data.data.columns}
                rows={data.data.rows}
                startIndex={offset}
                className="max-h-[62vh]"
              />
              <div className="flex items-center justify-between border-t border-border px-4 py-2.5">
                <p className="text-xs text-muted-foreground">
                  Showing <span className="font-mono text-foreground">{num(from)}</span>–
                  <span className="font-mono text-foreground">{num(to)}</span> of{" "}
                  <span className="font-mono text-foreground">{num(total)}</span>
                </p>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-muted-foreground">
                    Page {page} / {lastPage}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page <= 1 || data.loading}
                  >
                    <CaretLeft className="h-3.5 w-3.5" />
                    Prev
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.min(lastPage, p + 1))}
                    disabled={page >= lastPage || data.loading}
                  >
                    Next
                    <CaretRight className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            </>
          ) : (
            <EmptyState
              icon={TableIcon}
              title="No rows"
              description="This table is empty. Run the pipeline to ingest data first."
            />
          )}
        </LoadBoundary>
      </Card>
    </div>
  );
}
