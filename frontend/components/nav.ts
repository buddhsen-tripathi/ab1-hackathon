import {
  ChartBar,
  CloudArrowDown,
  FlowArrow,
  Users,
  type Icon,
} from "@phosphor-icons/react";

export interface NavItem {
  href: string;
  label: string;
  icon: Icon;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Pipeline", icon: FlowArrow },
  { href: "/ingestion", label: "Ingestion", icon: CloudArrowDown },
  { href: "/characterization", label: "Characterization", icon: ChartBar },
  { href: "/patients", label: "Patients", icon: Users },
];
