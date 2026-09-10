import type { CSSProperties, ReactNode } from "react";
import { RISK_ORDER } from "@/api/types";
import type { RiskLevel } from "@/api/types";
import type { InvestigationStatus } from "@/api/types";

interface BadgeProps {
  children?: ReactNode;
  className?: string;
  title?: string;
  style?: CSSProperties;
  "data-testid"?: string;
}

export function Badge({ children, className = "", title, style, "data-testid": testId }: BadgeProps) {
  return (
    <span className={`badge ${className}`} title={title} style={style} data-testid={testId}>
      {children}
    </span>
  );
}

const RISK_LABEL: Record<RiskLevel, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  unknown: "Unknown",
};

export function RiskBadge({ level, showDot = true }: { level: RiskLevel; showDot?: boolean }) {
  return (
    <Badge className={`risk-${level}`}>
      {showDot ? <span className="status-dot" aria-hidden /> : null}
      {RISK_LABEL[level]}
    </Badge>
  );
}

const STATUS_LABEL: Record<InvestigationStatus, string> = {
  draft: "Draft",
  open: "Open",
  investigating: "Investigating",
  review: "Pending Review",
  escalated: "Escalated",
  closed: "Closed",
};

const STATUS_CLASS: Record<InvestigationStatus, string> = {
  draft: "status-draft",
  open: "status-open",
  investigating: "status-investigating",
  review: "status-review",
  escalated: "status-escalated",
  closed: "status-closed",
};

export function StatusBadge({ status }: { status: InvestigationStatus }) {
  return <Badge className={STATUS_CLASS[status]}>{STATUS_LABEL[status]}</Badge>;
}

export function DemoBadge({ label = "DEMO DATA" }: { label?: string }) {
  return (
    <Badge className="badge-demo" title="This record is synthetic demo data, not real intelligence.">
      {label}
    </Badge>
  );
}

export function riskLabel(level: RiskLevel): string {
  return RISK_LABEL[level];
}

export { RISK_ORDER };
export type { RiskLevel };