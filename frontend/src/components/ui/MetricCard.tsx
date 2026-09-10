import type { ReactNode } from "react";
import { Badge, type RiskLevel } from "./Badges";
import { formatNumber } from "@/lib/format";

type Trend = "up" | "down" | "flat" | "none";

interface MetricCardProps {
  label: string;
  value?: ReactNode;
  desc?: ReactNode;
  trend?: Trend;
  trendLabel?: string;
  risk?: RiskLevel;
  awaiting?: boolean;
  sparkline?: number[];
  'data-testid'?: string;
}

export function MetricCard({
  label,
  value,
  desc,
  trend = "none",
  trendLabel,
  risk,
  awaiting,
  sparkline,
  "data-testid": testId,
}: MetricCardProps) {
  return (
    <article className={`metric-card ${awaiting ? "awaiting" : ""}`} data-testid={testId ?? `metric-${label}`}>
      {awaiting ? (
        <div className="metric-value">Awaiting data</div>
      ) : (
        <div className="metric-value">
          {value ?? "—"}
          {risk ? (
            <Badge className={`risk-${risk}`} title="Risk level">
              {risk.charAt(0).toUpperCase() + risk.slice(1)}
            </Badge>
          ) : null}
        </div>
      )}
      <div className="metric-label">{label}</div>
      {sparkline && !awaiting ? <Sparkline data={sparkline} /> : null}
      {trend !== "none" ? (
        <span className={`metric-trend trend-${trend}`}>
          {trend === "up" ? "↑" : trend === "down" ? "↓" : "→"} {trendLabel ?? ""}
        </span>
      ) : null}
      {desc ? <div className="metric-desc">{desc}</div> : null}
    </article>
  );
}

export function Sparkline({ data, width = 120, height = 28 }: { data: number[]; width?: number; height?: number }) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const stepX = width / (data.length - 1);
  const points = data.map((v, i) => {
    const x = i * stepX;
    const y = height - 3 - ((v - min) / range) * (height - 6);
    return `${x},${y}`;
  });
  return (
    <svg className="sparkline" width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden>
      <polyline
        points={points.join(" ")}
        fill="none"
        stroke="var(--primary)"
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

export interface MetricValueProps {
  value: number | null | undefined;
}

export function MetricNumber({ value }: MetricValueProps) {
  return <>{value === null || value === undefined ? "—" : formatNumber(value)}</>;
}