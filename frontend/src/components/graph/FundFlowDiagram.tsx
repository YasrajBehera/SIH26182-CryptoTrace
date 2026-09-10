import type { GraphNode, GraphPath } from "@/api/types";
import { Badge, DemoBadge } from "@/components/ui";
import { shortenAddress } from "@/lib/format";

const NODE_LABEL: Record<GraphNode["type"], string> = {
  wallet: "Wallet",
  contract: "Contract",
  vasp: "VASP/Exchange",
  unknown: "Unknown",
};

export function FundFlowDiagram({ path, demo, onNodeClick }: { path: GraphPath; demo?: boolean; onNodeClick?: (node: GraphNode) => void }) {
  const { nodes, edges, metrics } = path;

  if (!nodes.length) {
    return (
      <div className="state" role="status">
        <p className="state-title">No flow path</p>
        <p className="state-desc">Select a start and end entity to compute a path (requires Member 2 graph engine).</p>
      </div>
    );
  }

  return (
    <div className="stack">
      {demo ? <DemoBadge label="SYNTHETIC PATH — not computed" /> : null}

      <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))" }}>
        <Badge className="status-open">Path length: {metrics.pathLength}</Badge>
        <Badge className="status-open">Tx: {metrics.transactionCount}</Badge>
        <Badge className="status-open">Value: {metrics.totalValue} {metrics.asset}</Badge>
        <Badge className="status-open">Elapsed: {metrics.timeElapsed ?? "—"}</Badge>
        <Badge className="status-open">
          Confidence: {metrics.confidence !== null && metrics.confidence !== undefined ? `${metrics.confidence}%` : "unavailable"}
        </Badge>
      </div>

      <div style={{ display: "grid", justifyItems: "center", gap: 0 }} data-testid="fund-flow">
        {nodes.map((node, i) => {
          const edge = i < edges.length ? edges[i] : null;
          const body = (
            <div
              className="flow-step"
              style={{
                borderLeft: `3px solid ${
                  node.type === "vasp" ? "var(--green)" : node.risk === "high" || node.risk === "critical" ? "var(--red)" : "var(--primary)"
                }`,
                minWidth: 240,
              }}
            >
              <span className="mono" style={{ color: "var(--cyan)", fontSize: "var(--text-sm)" }}>
                {shortenAddress(node.address, 10, 6)}
              </span>
              <span style={{ marginLeft: "auto", textAlign: "right" }}>
                <Badge>{NODE_LABEL[node.type]}</Badge>
              </span>
            </div>
          );
          return (
            <div key={node.id} style={{ display: "grid", justifyItems: "center" }}>
              {onNodeClick ? (
                <button
                  type="button"
                  className="plain-hover"
                  style={{ background: "transparent", border: "none", padding: 0, cursor: "pointer" }}
                  onClick={() => onNodeClick(node)}
                  aria-label={`Open ${NODE_LABEL[node.type]} ${shortenAddress(node.address, 6, 4)} in graph`}
                >
                  {body}
                </button>
              ) : (
                body
              )}
              {edge ? (
                <div className="prov-link" aria-hidden>
                  ↓ {edge.amount} {edge.asset}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      <div className="risk-rule rr-high" role="note">
        <strong>Attribution caveat:</strong> the final hop toward a VASP is a candidate association. It does not
        establish ownership without corroborating backend evidence.
      </div>
    </div>
  );
}