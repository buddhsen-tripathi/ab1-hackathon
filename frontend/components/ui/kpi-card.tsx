import * as React from "react";
import type { Icon } from "@phosphor-icons/react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  label: string;
  value: React.ReactNode;
  hint?: string;
  icon?: Icon;
  className?: string;
}

export function KpiCard({ label, value, hint, icon: IconCmp, className }: KpiCardProps) {
  return (
    <Card className={cn("p-6", className)}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        {IconCmp && <IconCmp className="h-4 w-4 text-muted-foreground" />}
      </div>
      <div className="mt-3 font-mono text-[1.75rem] font-semibold leading-none tracking-tight tabular-nums text-foreground">
        {value}
      </div>
      {hint && <p className="mt-2 text-xs text-muted-foreground">{hint}</p>}
    </Card>
  );
}
