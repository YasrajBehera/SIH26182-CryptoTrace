import { useState } from "react";
import type { GraphEdge, GraphNode } from "@/api/types";
import { Card, RiskBadge, Badge, DemoBadge } from "@/components/ui";
import { Address } from "@/components/ui/Address";
import { formatAmount, formatNumber } from "@/lib/format";
import { TransferDrawer } from "@/components/transfers/TransferDrawer";
import { INJECTED_TRANSFER } from "@/mock/injected";

const TYPE_LABEL: Record<GraphNode["type"], string> = {
  wallet: "Wallet",
  contract: "Contract",
  vasp: "VASP / Exchange",
  unknown: "Unknown entity",
};

export function GraphNodePanel({
  node,
  edges,
  demo,
}: {
  node: GraphNode;
  edges: GraphEdge[];
  demo: boolean;
}) {
  const [openEdge, setOpenEdge] = useState<GraphEdge | null>(null);
  const adjacent = edges.filter((e) => e.source === node.id || e.target === node.id);

  return (
    <Card title="Selected entity" subtitle={`${TYPE_LABEL[node.type]} — ${node.id}`}>
      {demo ? <DemoBadge label="SYNTHETIC GRAPH" /> : <Badge>Live</Badge>}
      <div className="stack">
        <div className="detail-row">
          <span className="detail-label">Address</span>
          <span className="detail-value">
            <Address address={node.address} chain="eth" />
          </span>
        </div>
        <div className="detail-row">
          <span className="detail-label">Entity type</span>
          <span className="detail-value">{TYPE_LABEL[node.type]}</span>
        </div>
        <div className="detail-row">
          <span className="detail-label">Risk</span>
          <span className="detail-value">
            <RiskBadge level={node.risk} />
          </span>
        </div>
        <div className="detail-row">
          <span className="detail-label">Connections</span>
          <span className="detail-value">{formatNumber(adjacent.length)}</span>
        </div>
        <div className="detail-row">
          <span className="detail-label">Volume</span>
          <span className="detail-value">{node.metadata?.volume ? formatAmount(node.metadata.volume) : "—"}</span>
        </div>
      </div>

      {adjacent.length ? (
        <div>
          <p className="card-title-sm">Adjacent flows ({adjacent.length})</p>
          <div className="stack" style={{ gap: 6 }}>
            {adjacent.slice(0, 8).map((e) => (
              <button
                key={e.id}
                className="risk-rule rr-low"
                onClick={() => setOpenEdge(e)}
                style={{ cursor: "pointer", width: "100%", textAlign: "left", background: "var(--bg-elevated)" }}
              >
                <span className="mono" style={{ fontSize: 11, color: "var(--cyan)" }}>
                  {e.asset === "ETH" ? formatAmount(e.amount, e.asset) : `${e.amount} ${e.asset}`}
                </span>
                <span style={{ marginLeft: "auto", fontSize: "var(--text-xs)", color: "var(--text-faint)" }}>
                  {e.transactionHash.slice(0, 10)}…
                </span>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <TransferDrawer
        transfer={openEdge ? INJECTED_TRANSFER(openEdge) : null}
        onClose={() => setOpenEdge(null)}
      />
    </Card>
  );
}