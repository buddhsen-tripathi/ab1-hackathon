"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { List, Pulse, SidebarSimple, X } from "@phosphor-icons/react";
import { NAV_ITEMS } from "@/components/nav";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";

function Brand({ collapsed }: { collapsed?: boolean }) {
  return (
    <div
      className={cn(
        "flex items-center gap-2.5 px-3 py-1",
        collapsed && "justify-center px-0",
      )}
    >
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
        <Pulse className="h-4 w-4" weight="bold" />
      </div>
      {!collapsed && (
        <div className="min-w-0 leading-tight">
          <p className="truncate font-serif text-sm font-medium text-sidebar-foreground">
            ABI Pipeline
          </p>
          <p className="truncate text-[11px] text-sidebar-foreground/60">
            Wound-care billing
          </p>
        </div>
      )}
    </div>
  );
}

function NavLinks({
  collapsed,
  onNavigate,
}: {
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-1 px-2">
      {NAV_ITEMS.map((item) => {
        const active =
          item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            title={collapsed ? item.label : undefined}
            className={cn(
              "flex items-center gap-3 rounded-sm px-3 py-2.5 text-sm transition-colors",
              collapsed && "justify-center px-0",
              active
                ? "bg-sidebar-accent text-sidebar-foreground"
                : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
            )}
          >
            <Icon className="h-4 w-4 shrink-0" weight={active ? "fill" : "regular"} />
            {!collapsed && <span>{item.label}</span>}
          </Link>
        );
      })}
    </nav>
  );
}

function SidebarBody({
  collapsed,
  onToggleCollapse,
  onNavigate,
}: {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onNavigate?: () => void;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="px-2 py-4">
        <Brand collapsed={collapsed} />
      </div>
      <div className="no-scrollbar flex-1 overflow-y-auto pt-2">
        <NavLinks collapsed={collapsed} onNavigate={onNavigate} />
      </div>
      <div className="space-y-1 border-t border-sidebar-border p-2">
        <ThemeToggle collapsed={collapsed} />
        {onToggleCollapse && (
          <button
            type="button"
            onClick={onToggleCollapse}
            title={collapsed ? "Expand" : "Collapse"}
            className={cn(
              "hidden h-9 w-full items-center gap-3 rounded-sm px-3 py-2.5 text-sm text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground md:flex",
              collapsed && "justify-center px-0",
            )}
          >
            <SidebarSimple className="h-4 w-4 shrink-0" />
            {!collapsed && <span>Collapse</span>}
          </button>
        )}
      </div>
    </div>
  );
}

export function Sidebar() {
  const [open, setOpen] = React.useState(false);
  const [collapsed, setCollapsed] = React.useState(false);

  React.useEffect(() => {
    try {
      setCollapsed(localStorage.getItem("sidebar-collapsed") === "1");
    } catch {
      // ignore
    }
  }, []);

  const toggleCollapse = () => {
    setCollapsed((c) => {
      const next = !c;
      try {
        localStorage.setItem("sidebar-collapsed", next ? "1" : "0");
      } catch {
        // ignore
      }
      return next;
    });
  };

  return (
    <>
      {/* Desktop sidebar (collapsible) */}
      <aside
        className={cn(
          "hidden shrink-0 border-r border-sidebar-border bg-sidebar transition-[width] duration-200 md:block",
          collapsed ? "w-16" : "w-60",
        )}
      >
        <div className="sticky top-0 h-screen">
          <SidebarBody collapsed={collapsed} onToggleCollapse={toggleCollapse} />
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="fixed inset-x-0 top-0 z-30 flex h-14 items-center justify-between border-b border-sidebar-border bg-sidebar px-4 md:hidden">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Pulse className="h-4 w-4" weight="bold" />
          </div>
          <span className="font-serif text-sm font-medium">ABI Pipeline</span>
        </div>
        <button
          type="button"
          aria-label="Open menu"
          onClick={() => setOpen(true)}
          className="inline-flex h-9 w-9 items-center justify-center rounded-md text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground"
        >
          <List className="h-5 w-5" />
        </button>
      </div>

      {/* Mobile drawer */}
      <AnimatePresence>
        {open && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={() => setOpen(false)}
              className="fixed inset-0 z-40 bg-black/60 md:hidden"
            />
            <motion.aside
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "tween", duration: 0.2 }}
              className="fixed inset-y-0 left-0 z-50 w-64 border-r border-sidebar-border bg-sidebar md:hidden"
            >
              <button
                type="button"
                aria-label="Close menu"
                onClick={() => setOpen(false)}
                className="absolute right-3 top-4 inline-flex h-8 w-8 items-center justify-center rounded-md text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground"
              >
                <X className="h-4 w-4" />
              </button>
              <SidebarBody onNavigate={() => setOpen(false)} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
