"use client";

import * as React from "react";
import { WarningCircle } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { API_BASE } from "@/lib/api";

interface LoadBoundaryProps {
  loading: boolean;
  error: string | null;
  onRetry?: () => void;
  skeleton?: React.ReactNode;
  children: React.ReactNode;
}

/** Standard loading / error wrapper so every page handles async the same way. */
export function LoadBoundary({
  loading,
  error,
  onRetry,
  skeleton,
  children,
}: LoadBoundaryProps) {
  if (loading) {
    return (
      <>
        {skeleton ?? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-28" />
            ))}
          </div>
        )}
      </>
    );
  }

  if (error) {
    return (
      <EmptyState
        icon={WarningCircle}
        title="Could not reach the pipeline API"
        description={`${error}. Make sure the backend is running at ${API_BASE}.`}
        action={
          onRetry ? (
            <Button variant="outline" onClick={onRetry}>
              Retry
            </Button>
          ) : undefined
        }
      />
    );
  }

  return <>{children}</>;
}
