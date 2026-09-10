import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { PageHeader, Button, Card, Input, Select, DemoBadge, Badge, Tabs, ErrorState, LoadingBlock } from "@/components/ui";
import { GraphCanvas } from "@/components/graph/GraphCanvas";
import { GraphNodePanel } from "@/components/graph/GraphNodePanel";
import { FundFlowDiagram } from "@/components/graph/FundFlowDiagram";
import { useApi } from "@/hooks/useApi";
import { graph } from "@/api/graph";
import { useDataSource } from "@/app/DataSourceContext";
import { useAuth } from "@/auth/AuthContext";
import type { GraphNode, GraphEdge } from "@/api/types";
import { validateAddressInput } from "@/lib/address";
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
  const [activeTab, setActiveTab] = useState(params.get("tab") === "flow" ? "flow" : "graph");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);

  const timeRangeDays = useMemo(() => {
    if (timeRange === "30") return 30;
    if (timeRange === "90") return 90;
    if (timeRange === "365") return 365;
    return null;
  }, [timeRange]);

  const validAddress = !address || validateAddressInput(address) === null;

  const { data: graphData, loading, error, reload } = useApi(
    () =>
      validAddress && address
        ? graph.query({ address, network: "ethereum", depth: Number(depth) || 2, timeRangeDays })
        : Promise.reject(new Error("Enter a valid wallet address first.")),
    [address, depth, timeRangeDays],
    { enabled: validAddress && !!address },
  );

  const { data: flowPath } = useApi(
    () => (validAddress && address ? graph.path(address, `${address.slice(0, 10)}_f`) : Promise.reject(new Error("Enter a wallet address."))),
    [address],
    { enabled: validAddress && !!address },
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

  const tabs: TabItem[] = [
    { key: "graph", label: "Graph" },
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
        subtitle="Visualize wallet relationships and fund flows. Graph data is synthetic until the Member 2 graph engine ships."
        crumbs={[{ label: "Transaction Graph" }]}
        actions={isDemo ? <DemoBadge label="SYNTHETIC GRAPH DATA" /> : <Badge className="status-open">Live</Badge>}
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
              Graph engine (Member 2) is not reachable — live queries are unavailable.
            </span>
          ) : null}
        </form>
      </Card>

      <Tabs tabs={tabs} active={activeTab} onChange={setActiveTab} />

      {activeTab === "graph" ? (
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
                "Enter a valid wallet address on the Ethereum network to query the (synthetic today) graph adapter."
              }
              action={address ? <Button onClick={reload}>Retry</Button> : undefined}
            />
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
                  <GraphNodePanel node={selectedNode ?? graphData.nodes[0]} edges={graphData.edges} demo={isDemo} />
                  {selectedEdge ? (
                    <Card title="Selected edge" subtitle={`${selectedEdge.asset} flow`}>
                      <div className="stack">
                        <span className="mono">{selectedEdge.transactionHash}</span>
                        <Badge className="status-open">{selectedEdge.amount} {selectedEdge.asset}</Badge>
                        <span className="text-dim">
                          {selectedEdge.source.slice(0, 8)}… → {selectedEdge.target.slice(0, 8)}…
                        </span>
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
        <Card title="Discrete fund flow" subtitle="Synthetic path reconstruction. Not computed from live chain data.">
          {flowPath ? (
            <FundFlowDiagram
              path={flowPath}
              demo={isDemo}
              onNodeClick={(n) => navigate(`/graph?address=${encodeURIComponent(n.address)}`)}
            />
          ) : (
            <LoadingBlock />
          )}
        </Card>
      )}
    </div>
  );
}