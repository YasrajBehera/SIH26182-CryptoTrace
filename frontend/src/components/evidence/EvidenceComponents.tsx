import type { EvidenceItem, ProvenanceLink } from "@/api/types";
import { Card, Badge, DemoBadge, Address } from "@/components/ui";
import { formatDate } from "@/lib/format";

const TYPE_LABEL: Record<EvidenceItem["type"], string> = {
  blockchain_transaction: "Blockchain transaction",
  address_intelligence: "Address intelligence",
  screenshot: "Screenshot",
  document: "Document",
  external_source: "External source",
  analyst_note: "Analyst note",
  system_observation: "System observation",
};

const RELIABILITY_CLASS: Record<EvidenceItem["reliability"], string> = {
  verified: "status-success",
  high: "status-investigating",
  medium: "status-pending",
  low: "status-draft",
};

export function EvidenceCard({
  item,
  focused,
  onDelete,
}: {
  item: EvidenceItem;
  focused?: boolean;
  onDelete?: (item: EvidenceItem) => void;
}) {
  return (
    <Card
      id={`evidence-${item.id}`}
      className={focused ? "evidence-focused" : undefined}
      title={
        <span className="row" style={{ gap: 8 }}>
          {item.id} — {item.title}
          {item.isDemo ? <DemoBadge /> : null}
        </span>
      }
      subtitle={TYPE_LABEL[item.type]}
      actions={
        <span className="row" style={{ gap: 8 }}>
          <Badge className={RELIABILITY_CLASS[item.reliability]}>Reliability: {item.reliability}</Badge>
          {onDelete ? (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => onDelete(item)}>
              Delete
            </button>
          ) : null}
        </span>
      }
      bodyClassName="stack"
    >
      <div className="detail-grid">
        <div className="stack">
          <div className="detail-row">
            <span className="detail-label">Source</span>
            <span className="detail-value">{item.source}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Created by</span>
            <span className="detail-value">{item.createdBy}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Created at</span>
            <span className="detail-value">{formatDate(item.createdAt)}</span>
          </div>
        </div>
        <div className="stack">
          {item.relatedWallet ? (
            <div className="detail-row">
              <span className="detail-label">Related wallet</span>
              <span className="detail-value">
                <Address address={item.relatedWallet} chain="eth" silent />
              </span>
            </div>
          ) : null}
          {item.relatedTransaction ? (
            <div className="detail-row">
              <span className="detail-label">Related tx</span>
              <span className="detail-value mono" style={{ fontSize: 11.5 }}>
                {item.relatedTransaction.slice(0, 18)}…
              </span>
            </div>
          ) : null}
          {item.relatedCandidate ? (
            <div className="detail-row">
              <span className="detail-label">Related candidate</span>
              <span className="detail-value">{item.relatedCandidate}</span>
            </div>
          ) : null}
          {item.checksum ? (
            <div className="detail-row">
              <span className="detail-label">Hash / checksum</span>
              <span className="detail-value mono" style={{ fontSize: 11.5 }}>{item.checksum}</span>
            </div>
          ) : null}
        </div>
      </div>
      {item.notes ? <p style={{ margin: 0, fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>{item.notes}</p> : null}
    </Card>
  );
}

export function ProvenanceChain({ links }: { links: ProvenanceLink[] }) {
  return (
    <div className="stack" data-testid="provenance-chain">
      {links.map((l, i) => (
        <div key={l.id}>
          <div className="prov-node">
            <span className="badge" aria-hidden>{l.kind.toUpperCase()}</span>
            <div>
              <div style={{ fontWeight: 600, fontSize: "var(--text-sm)" }}>{l.label}</div>
              {l.sublabel ? <div style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)" }}>{l.sublabel}</div> : null}
            </div>
          </div>
          {i < links.length - 1 ? <div className="prov-link">↓ derived from</div> : null}
        </div>
      ))}
    </div>
  );
}