import type { ConfidenceLevel } from "@/api/types";
import { clamp } from "@/lib/format";

const LABEL: Record<ConfidenceLevel, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
  unknown: "Unknown",
};

export function ConfidenceLevelBadge({ level }: { level: ConfidenceLevel }) {
  return <span className={`conf-level conf-${level}`}>{LABEL[level]}</span>;
}

interface ConfidenceIndicatorProps {
  level: ConfidenceLevel;
  /** Raw percentage when the backend provides a real score; null/undefined otherwise. */
  score?: number | null;
  hideBadge?: boolean;
}

export function ConfidenceIndicator({ level, score, hideBadge }: ConfidenceIndicatorProps) {
  const hasScore = typeof score === "number" && Number.isFinite(score);
  const pct = hasScore ? clamp(Math.round(score as number), 0, 100) : 0;

  return (
    <div className={`confidence conf-${level}`}>
      <div className="confidence-label">
        <span>{hideBadge ? null : LABEL[level]}</span>
        <span>{hasScore ? `${pct}%` : "Score unavailable"}</span>
      </div>
      <div className="confidence-bar" role="img" aria-label={`${LABEL[level]}${hasScore ? `: ${pct}%` : " — score unavailable"}`}>
        {hasScore ? <div className="confidence-fill" style={{ width: `${pct}%` }} /> : null}
      </div>
    </div>
  );
}