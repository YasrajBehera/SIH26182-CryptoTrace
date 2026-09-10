import { useState } from "react";
import type { AttributionCandidate } from "@/api/types";
import { Card, Badge, DemoBadge, RiskBadge, Address, ConfidenceLevelBadge } from "@/components/ui";
import { ConfidenceIndicator } from "@/components/ui/Confidence";
import { formatDate } from "@/lib/format";

const STATE_LABEL: Record<AttributionCandidate["state"], string> = {
  not_analyzed: "Not analyzed",
  analysis_pending: "Analysis pending",
  no_attribution: "No attribution available",
  candidate_detected: "Candidate detected",
  evidence_insufficient: "Evidence insufficient",
  high_confidence: "High-confidence association",
  medium_confidence: "Medium-confidence association",
  low_confidence: "Low-confidence association",
};

export function candidateStateLabel(state: AttributionCandidate["state"]): string {
  return STATE_LABEL[state];
}

export function CandidateCard({ candidate }: { candidate: AttributionCandidate }) {
  const [open, setOpen] = useState(false);

  return (
    <Card
      title={
        <span className="row" style={{ gap: 8 }}>
          {candidate.vaspName}
          {candidate.isDemo ? <DemoBadge /> : null}
        </span>
      }
      subtitle={candidateStateLabel(candidate.state)}
      bodyClassName="stack"
    >
      <div className="detail-grid">
        <div className="stack">
          <div className="detail-row">
            <span className="detail-label">Wallet</span>
            <span className="detail-value">
              <Address address={candidate.wallet} chain="eth" silent />
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Confidence</span>
            <span className="detail-value">
              <ConfidenceLevelBadge level={candidate.confidenceLevel} />
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Evidence items</span>
            <span className="detail-value">{candidate.evidenceCount}</span>
          </div>
        </div>
        <div className="stack">
          <div className="detail-row">
            <span className="detail-label">Volume</span>
            <span className="detail-value">{candidate.transactionVolume} {candidate.asset}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">First / last interaction</span>
            <span className="detail-value">
              {formatDate(candidate.firstInteraction)} → {formatDate(candidate.lastInteraction)}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Risk</span>
            <span className="detail-value">
              <RiskBadge level={candidate.risk} />
            </span>
          </div>
        </div>
      </div>

      <div className="card" style={{ background: "var(--bg-elevated)" }}>
        <p style={{ margin: 0 }}>
          <strong>Reasoning:</strong> {candidate.reasoning}
        </p>
      </div>

      <ConfidenceIndicator level={candidate.confidenceLevel} score={candidate.confidenceScore} />

      {candidate.relatedAddresses.length ? (
        <div>
          <p className="card-title-sm">Related addresses</p>
          <div className="row">
            {candidate.relatedAddresses.map((a) => (
              <Badge key={a} className="status-open">
                <span className="mono">{a.slice(0, 10)}…</span>
              </Badge>
            ))}
          </div>
        </div>
      ) : null}

      <button className="btn btn-ghost btn-sm" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {open ? "Hide" : "View"} attribution factors
      </button>

      {open ? (
        <div className="stack">
          {candidate.factors.length ? (
            candidate.factors.map((f) => (
              <div key={f.id} className="factor-row">
                <div>
                  <div className="factor-name">{f.factor}</div>
                  <div className="factor-evidence">{f.evidence}</div>
                  <div className="factor-evidence">Source: {f.source}</div>
                </div>
                <span className="conf-level conf-unknown">
                  {f.confidenceContribution !== null && f.confidenceContribution !== undefined
                    ? `${f.confidenceContribution} pts`
                    : "no score"}
                </span>
              </div>
            ))
          ) : (
            <p style={{ color: "var(--text-faint)", fontSize: "var(--text-sm)", margin: 0 }}>
              No factor breakdown available — requires the Member 3 attribution engine.
            </p>
          )}
        </div>
      ) : null}
    </Card>
  );
}