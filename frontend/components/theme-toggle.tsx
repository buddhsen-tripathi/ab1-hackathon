"use client";

import * as React from "react";
import { Moon, Sun } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";

export function ThemeToggle({
  className,
  collapsed,
}: {
  className?: string;
  collapsed?: boolean;
}) {
  const [dark, setDark] = React.useState(false);

  React.useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {
      // ignore
    }
  };

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label="Toggle theme"
      title={collapsed ? (dark ? "Dark mode" : "Light mode") : undefined}
      className={cn(
        "inline-flex h-9 w-full items-center gap-3 rounded-sm px-3 py-2.5 text-sm text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        collapsed && "justify-center px-0",
        className,
      )}
    >
      {dark ? <Moon className="h-4 w-4 shrink-0" /> : <Sun className="h-4 w-4 shrink-0" />}
      {!collapsed && <span>{dark ? "Dark" : "Light"} mode</span>}
    </button>
  );
}
