import type { RiskLevel } from "@/api/types";
import { RISK_ORDER } from "@/api/types";

const RISK_COLOR: Record<RiskLevel, string> = {
  critical: "var(--red)",
  high: "var(--red)",
  medium: "var(--amber)",
  low: "var(--green)",
  unknown: "var(--gray)",
};

/**
 * Hand-rolled SVG charts — no chart library dependency.
 * Charts are only shown when real data exists; otherwise the UI shows the
 * "Awaiting data" state.
 */
export function RiskBarChart({
  data,
  total,
  testid,
}: {
  data: Array<{ level: RiskLevel; count: number }>;
  total: number;
  testid?: string;
}) {
  const max = Math.max(1, ...data.map((d) => d.count));
  return (
    <div data-testid={testid} className="stack">
      {data.map((d) => (
        <div key={d.level} className="grid" style={{ gridTemplateColumns: "52px 1fr 36px", alignItems: "center", gap: 8 }}>
          <span className="stat-inline" style={{ fontWeight: 600 }}>
            {d.level.charAt(0).toUpperCase() + d.level.slice(1)}
          </span>
          <div className="confidence-bar">
            <div
              className="confidence-fill"
              style={{ width: `${total ? Math.round((d.count / max) * 100) : 0}%`, background: RISK_COLOR[d.level] }}
            />
          </div>
          <span className="mono" style={{ textAlign: "right", color: "var(--text-muted)" }}>
            {d.count}
          </span>
        </div>
      ))}
    </div>
  );
}

export function RiskRing({
  counts,
  total,
  size = 180,
}: {
  counts: Array<{ level: RiskLevel; count: number }>;
  total: number;
  size?: number;
}) {
  const r = size / 2 - 14;
  const c = 2 * Math.PI * r;
  const segments = counts.map((d) => {
    const frac = total ? d.count / total : 0;
    return { ...d, frac };
  });

  let acc = 0;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Risk distribution">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--bg-raised)" strokeWidth="12" />
      {segments.map((s) => {
        const dash = s.frac * c;
        const el = (
          <circle
            key={s.level}
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={RISK_COLOR[s.level]}
            strokeWidth="12"
            strokeDasharray={`${dash} ${c - dash}`}
            strokeDashoffset={-acc * c}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
          />
        );
        acc += s.frac;
        return el;
      })}
      <text x="50%" y="47%" textAnchor="middle" fill="var(--text)" fontSize="26" fontWeight="700">
        {total}
      </text>
      <text x="50%" y="58%" textAnchor="middle" fill="var(--text-faint)" fontSize="11">
        flagged wallets
      </text>
    </svg>
  );
}

/** Tiny monotone sparkline used in KPI cards. */
export function sparkline(min: number, max: number, points: number[]): string {
  if (points.length < 2) return "";
  const range = max - min || 1;
  const step = 100 / (points.length - 1);
  return points.map((v, i) => `${(i * step).toFixed(1)},${(100 - ((v - min) / range) * 100).toFixed(1)}`).join(" ");
}

export { RISK_ORDER };