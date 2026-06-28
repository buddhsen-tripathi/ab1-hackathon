import { ClipboardText, FlowArrow, Table, Waveform, type Icon } from "@phosphor-icons/react";

export interface NavItem {
  href: string;
  label: string;
  icon: Icon;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Pipeline", icon: FlowArrow },
  { href: "/worklist", label: "Worklist", icon: ClipboardText },
  { href: "/signals", label: "Signals", icon: Waveform },
  { href: "/data", label: "Data", icon: Table },
];
