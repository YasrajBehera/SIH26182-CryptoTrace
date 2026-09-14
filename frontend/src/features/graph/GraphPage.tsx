import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { PageHeader, Button, Card, Input, Select, DemoBadge, Badge, Tabs, ErrorState, LoadingBlock } from "@/components/ui";
import { GraphCanvas } from "@/components/graph/GraphCanvas";
import { GraphNodePanel } from "@/components/graph/GraphNodePanel";
import { FundFlowDiagram } from "@/components/graph/FundFlowDiagram";
import { FocusedGraph } from "@/components/graph/FocusedGraph";
import { useApi } from "@/hooks/useApi";
import { graph, toWalletId } from "@/api/graph";
import { getDemoPath } from "@/mock";
import { useDataSource } from "@/app/DataSourceContext";
import { useAuth } from "@/auth/AuthContext";
import type { GraphNode, GraphEdge } from "@/api/types";
import { validateAddressInput } from "@/lib/address";
import { formatTimestamp, shortenAddress } from "@/lib/format";
import type { TabItem } from "@/components/ui";

const LEGEND = [
  { label: "Wallet", swatchClass: "dot-wallet", hint: "external wallet address" },
  { label: "Contract", swatchClass: "dot-contract", hint: "smart-contract address" },
  { label: "VASP", swatchClass: "dot-vasp", hint: "possible service-provider endpoint" },
  { label: "Unknown", swatchClass: "dot-unknown", hint: "no classification available" },
];

export function GraphPage() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const { isDemo } = useDataSource();
  const { can } = useAuth();

  const paramsAddress = params.get("address") ?? "";
  const [address, setAddress] = useState(paramsAddress);
  const [depth, setDepth] = useState("2");
  const [timeRange, setTimeRange] = useState("all");
  const [activeTab, setActiveTab] = useState<"graph" | "flow" | "focused">(params.get("tab") === "flow" ? "flow" : params.get("tab") === "focused" ? "focused" : "graph");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);

  const timeRangeDays = useMemo(() => {
    if (timeRange === "30") return 30;
    if (timeRange === "90") return 90;
    if (timeRange === "365") return 365;
    return null;
  }, [timeRange]);

  const validAddress = !address || validateAddressInput(address) === null;

  // Honest provider detection: in live mode we probe the backend graph health
  // endpoint once. Only when the backend reports Neo4j as reachable ("ok") do
  // we label the page LIVE. Otherwise everything shown is synthetic.
  const { data: graphHealth } = useApi(() => graph.health(), [], { enabled: !isDemo });
  const provider = isDemo ? "synthetic" : graphHealth?.provider ?? "checking";

  // Synthetic topology is ONLY ever rendered in demo mode. In live mode an
  // unreachable graph engine is surfaced as an error — never as fake data.
  const useSynthetic = isDemo;
  const graphUnavailable = !isDemo && provider === "synthetic";

  const { data: graphData, loading, error, reload } = useApi(
    () => {
      if (!validAddress || !address) return Promise.reject(new Error("Enter a valid wallet address first."));
      if (graphUnavailable) {
        return Promise.reject(
          new Error("GRAPH ENGINE UNAVAILABLE — the Neo4j graph engine is not reachable. No synthetic topology is shown while the live engine is down. Start the graph service, then retry."),
        );
      }
      return graph.query({ address, network: "ethereum", depth: Number(depth) || 2, timeRangeDays });
    },
    [address, depth, timeRangeDays, useSynthetic, graphUnavailable],
    { enabled: validAddress && !!address && activeTab !== "focused" },
  );

  // Focused (mini-graph) data is fetched independently at depth 1 so a compact
  // neighbourhood can be inspected without loading a deeper full graph first.
  const {
    data: focusedData,
    loading: focusedLoading,
    error: focusedError,
    reload: reloadFocused,
  } = useApi(
    () => graph.query({ address, network: "ethereum", depth: 1, timeRangeDays }),
    [address, timeRangeDays, useSynthetic, graphUnavailable],
    { enabled: activeTab === "focused" && validAddress && !!address && !graphUnavailable },
  );
  // Fund-flow destination: explicit `?to=` marks the path end. Otherwise the
  // strongest counterparty (largest recorded amount) from the live graph is
  // auto-selected so the flow tab renders without manual URL editing. Demo
  // mode keeps a labeled demo target.
  const toParam = params.get("to") ?? "";
  const flowTarget = useMemo(() => {
    if (toParam) return toParam;
    if (isDemo) return `${(address ?? "").slice(0, 10)}_f`;
    if (!graphData || !address) return "";
    const srcId = toWalletId(address, "ethereum");
    let best = "";
    let bestAmount = -1;
    graphData.edges.forEach((e) => {
      const amount = Number(e.amount);
      if (!Number.isFinite(amount)) return;
      const other = e.source === srcId ? e.target : e.target === srcId ? e.source : "";
      if (!other || amount <= bestAmount) return;
      bestAmount = amount;
      best = other.split(":").pop() ?? other;
    });
    return best;
  }, [toParam, isDemo, graphData, address]);

  const { data: flowPath, loading: flowLoading, error: flowError, reload: reloadFlow } = useApi(
    () => {
      if (!validAddress || !address || !flowTarget) {
        return Promise.reject(
          graphUnavailable
            ? new Error("GRAPH ENGINE UNAVAILABLE — the Neo4j graph engine is not reachable, so no fund flow can be computed.")
            : new Error("Add a destination (?to=...) to compute a fund-flow path."),
        );
      }
      if (graphUnavailable) {
        return Promise.reject(
          new Error("GRAPH ENGINE UNAVAILABLE — the Neo4j graph engine is not reachable, so no fund flow can be computed."),
        );
      }
      return useSynthetic ? Promise.resolve(getDemoPath()) : graph.path(address, flowTarget);
    },
    [address, flowTarget, useSynthetic, graphUnavailable],
    { enabled: validAddress && !!address && !!flowTarget },
  );

  const providerBadge = isDemo ? (
    <DemoBadge label="SYNTHETIC GRAPH DATA" />
  ) : provider === "neo4j" ? (
    <Badge className="status-open">Live — Neo4j graph engine</Badge>
  ) : provider === "checking" ? (
    <Badge className="status-pending">Probing graph engine…</Badge>
  ) : (
    <Badge className="status-draft">Graph engine unavailable</Badge>
  );

  const highlighted = useMemo(() => {
    if (!selectedNode || !graphData) return undefined;
    const set = new Set<string>();
    graphData.edges.forEach((e) => {
      // Highlight both incoming and outgoing edges of the selected entity so
      // upstream fund sources and downstream exits are equally traceable.
      if (e.source === selectedNode.id || e.target === selectedNode.id) set.add(e.id);
    });
    return set;
  }, [selectedNode, graphData]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validAddress || !address) return;
    setParams({ address });
  };

  const focusCenter = useMemo(() => {
    const data = activeTab === "focused" ? (focusedData ?? graphData) : graphData;
    if (!data || data.nodes.length === 0) return undefined;
    const q = (address ?? "").toLowerCase();
    return data.nodes.find((n) => n.address.toLowerCase() === q);
  }, [graphData, focusedData, address, activeTab]);

  const tabs: TabItem[] = [
    { key: "graph", label: "Graph" },
    { key: "focused", label: "Focused" },
    { key: "flow", label: "Fund flow" },
  ];

  if (!can("graph.read")) {
    return (
      <div className="page">
        <PageHeader title="Transaction Graph" />
        <Card>
          <p style={{ color: "var(--text-muted)" }}>Your role does not permit graph analysis.</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        title="Transaction Graph"
        subtitle={
          provider === "neo4j"
            ? "Visualize wallet relationships and fund flows against the live Neo4j graph engine."
            : isDemo
              ? "Demo mode — synthetic graph topology is shown to exercise the interface."
              : "The graph engine is not currently reachable. No synthetic topology is shown in live mode."
        }
        crumbs={[{ label: "Transaction Graph" }]}
        actions={providerBadge}
      />

      <Card title="Graph query">
        <form className="row" style={{ gap: 8, flexWrap: "wrap" }} onSubmit={submit}>
          <Input
            className="mono"
            style={{ flex: "1 1 320px", maxWidth: 420 }}
            placeholder="0x… wallet address"
            value={address}
            invalid={!validAddress}
            onChange={(e) => setAddress(e.target.value)}
            aria-label="Wallet address for graph query"
          />
          <Select value={depth} onChange={(e) => setDepth(e.target.value)} aria-label="Graph depth" style={{ maxWidth: 120 }}>
            <option value="1">Depth 1</option>
            <option value="2">Depth 2</option>
            <option value="3">Depth 3</option>
          </Select>
          <Select value={timeRange} onChange={(e) => setTimeRange(e.target.value)} aria-label="Time range" style={{ maxWidth: 150 }}>
            <option value="all">All time</option>
            <option value="30">Last 30 days</option>
            <option value="90">Last 90 days</option>
            <option value="365">Last 365 days</option>
          </Select>
          <Button variant="primary" type="submit" disabled={!validAddress || !address}>
            Build graph
          </Button>
          <Button variant="ghost" type="button" onClick={reload}>
            ↻ Reload
          </Button>
          {!isDemo ? (
            <span style={{ color: "var(--text-faint)", fontSize: "var(--text-xs)", alignSelf: "center" }}>
              {provider === "neo4j"
                ? "Live graph engine queried on build via the backend graph API (Neo4j)."
                : graphUnavailable
                  ? "Graph engine unreachable — queries are not answered in live mode until Neo4j is back."
                  : "Probing the graph engine…"}
            </span>
          ) : null}
        </form>
      </Card>

      <Tabs tabs={tabs} active={activeTab} onChange={(k) => setActiveTab(k as typeof activeTab)} />

      {activeTab === "focused" ? (
        <Card
          title="Focused view"
          subtitle={
            provider === "neo4j"
              ? "Immediate depth-1 neighbourhood around the subject wallet — the live Neo4j data, rendered as a compact read-only diagram."
              : isDemo
                ? "Synthetic depth-1 neighbourhood — demo topology, not live chain data."
                : "A focused view is not available — the graph engine is not reachable."
          }
          actions={
            address && validAddress ? (
              <Button variant="ghost" size="sm" onClick={() => setActiveTab("graph")}>
                Open in full graph →
              </Button>
            ) : undefined
          }
        >
          {focusedLoading ? (
            <div style={{ height: 240 }}>
              <LoadingBlock />
            </div>
          ) : focusedError || !focusedData ? (
            <ErrorState
              title="Unable to build graph"
              description={focusedError ?? "Enter a valid wallet address to view its neighbourhood."}
              action={address ? <Button onClick={reloadFocused}>Retry</Button> : undefined}
            />
          ) : focusedData.nodes.length === 0 ? (
            <div className="state" role="status">
              <p className="state-title">No graph data</p>
              <p className="state-desc">No transactions are recorded in the graph engine for this wallet yet.</p>
            </div>
          ) : focusCenter ? (
            <div className="stack" data-testid="focused-section">
              <FocusedGraph
                nodes={focusedData.nodes}
                edges={focusedData.edges}
                centerId={focusCenter.id}
                height={240}
                onNodeClick={(n) => {
                  setSelectedNode(n);
                  setActiveTab("graph");
                }}
              />
              <p className="text-dim" style={{ margin: 0, fontSize: "var(--text-xs)" }}>
                Center: {shortenAddress(focusCenter.address)} · neighbours shown up to 12 · click a node to open it in the full graph.
              </p>
            </div>
          ) : (
            <div className="state" role="status">
              <p className="state-title">No focus node</p>
              <p className="state-desc">The selected wallet is not present in the returned graph, so no focused view can be drawn.</p>
            </div>
          )}
        </Card>
      ) : activeTab === "graph" ? (
        <Card title="Relationship graph" subtitle="Click a node for details; click an edge to view the recorded transfer.">
          {loading ? (
            <div style={{ height: 420 }}>
              <LoadingBlock />
            </div>
          ) : error || !graphData ? (
            <ErrorState
              title="Unable to build graph"
              description={
                error ??
                "Enter a valid wallet address on the Ethereum network. The graph engine is unavailable, so no topology data can be reconstructed."
              }
              action={address ? <Button onClick={reload}>Retry</Button> : undefined}
            />
          ) : graphData && graphData.nodes.length === 0 ? (
            <div className="state" role="status">
              <p className="state-title">No graph data</p>
              <p className="state-desc">
                No transactions are recorded in the graph engine for this wallet yet. Analyze the wallet, then sync
                the graph (live analyses are mirrored automatically when Neo4j is reachable).
              </p>
              {address ? <Button onClick={reload}>Retry</Button> : null}
            </div>
          ) : (
            <>
              <div className="grid" style={{ gridTemplateColumns: "minmax(0,1fr) 300px", gap: 16 }} data-testid="graph-layout">
                <GraphCanvas
                  nodes={graphData.nodes}
                  edges={graphData.edges}
                  highlightedPathIds={highlighted}
                  fitView
                  onSelectNode={setSelectedNode}
                  onSelectEdge={setSelectedEdge}
                  height="520px"
                  testid="graph-canvas"
                />
                <div>
                  <GraphNodePanel node={selectedNode ?? graphData.nodes[0]} edges={graphData.edges} demo={useSynthetic} />
                  {selectedEdge ? (
                    <Card title="Selected edge" subtitle={`${selectedEdge.asset} flow`}>
                      <div className="stack">
                        <span className="mono">{selectedEdge.transactionHash}</span>
                        <Badge className="status-open">{selectedEdge.amount} {selectedEdge.asset}</Badge>
                        <span className="text-dim">
                          {selectedEdge.source.slice(0, 8)}… → {selectedEdge.target.slice(0, 8)}…
                        </span>
                        <span className="text-dim" style={{ fontSize: "var(--text-xs)" }}>
                          Block {selectedEdge.blockNumber ?? "—"}
                        </span>
                        {selectedEdge.timestamp ? (
                          <span className="text-dim" style={{ fontSize: "var(--text-xs)" }}>
                            {formatTimestamp(selectedEdge.timestamp)} ·{" "}
                            {useSynthetic ? "Synthetic timestamp · Source: Demo data" : "Blockchain timestamp · Source: Ethereum"}
                          </span>
                        ) : (
                          <span className="text-dim" style={{ fontSize: "var(--text-xs)" }}>
                            Timestamp unavailable
                          </span>
                        )}
                      </div>
                    </Card>
                  ) : null}
                </div>
              </div>
              <div className="row" style={{ gap: 14, flexWrap: "wrap", marginTop: 8 }} aria-label="Graph node legend">
                {LEGEND.map((item) => (
                  <span key={item.label} className="row" style={{ gap: 6 }}>
                    <span className={item.swatchClass} style={{ width: 10, height: 10, borderRadius: "50%" }} aria-hidden />
                    <span style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)" }}>
                      <strong>{item.label}</strong> — {item.hint}
                    </span>
                  </span>
                ))}
              </div>
            </>
          )}
        </Card>
      ) : (
        <Card
          title="Fund Flow"
          subtitle={
            provider === "neo4j"
              ? "Reconstructs movement of funds across the live Neo4j transaction graph."
              : isDemo
                ? "Synthetic path reconstruction — demo topology, not live chain data."
                : "Fund flow cannot be computed — the graph engine is not reachable."
          }
        >
          {flowLoading ? (
            <div style={{ height: 420 }}>
              <LoadingBlock />
            </div>
          ) : flowError || !flowPath ? (
            <ErrorState
              title="Unable to compute fund flow"
              description={flowError ?? "Enter a valid wallet address to trace a fund path."}
              action={address && flowTarget ? <Button onClick={reloadFlow}>Retry</Button> : undefined}
            />
          ) : (
            <FundFlowDiagram
              path={flowPath}
              demo={useSynthetic}
              onNodeClick={(n) => navigate(`/graph?address=${encodeURIComponent(n.address)}`)}
            />
          )}
        </Card>
      )}
    </div>
  );
}