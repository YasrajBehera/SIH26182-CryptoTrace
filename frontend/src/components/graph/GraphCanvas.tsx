import { useMemo } from "react";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  Handle,
  Position,
  MarkerType,
} from "@xyflow/react";
import type { Node, Edge, NodeProps, NodeTypes } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { GraphEdge, GraphNode } from "@/api/types";
import { shortenAddress } from "@/lib/format";
import { riskLabel } from "@/components/ui/Badges";

const TYPE_LABEL: Record<GraphNode["type"], string> = {
  wallet: "Wallet",
  contract: "Contract",
  vasp: "VASP",
  unknown: "Unknown",
};

const NODE_TO_CLASS: Record<GraphNode["type"], string> = {
  wallet: "node-wallet",
  contract: "node-contract",
  vasp: "node-vasp",
  unknown: "node-unknown",
};

export const NODE_RISK_CLASS: Record<GraphNode["risk"], string> = {
  critical: "high-risk",
  high: "high-risk",
  medium: "",
  low: "",
  unknown: "",
};

function GraphNodeComponent({ data, selected }: NodeProps) {
  const node = data as unknown as GraphNode & { clickable?: boolean };
  const cls = [
    "graph-node",
    NODE_TO_CLASS[node.type],
    node.risk === "critical" || node.risk === "high" ? "high-risk" : "",
    selected ? "selected" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <>
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <div className={cls} data-testid={`graph-node-${node.id}`}>
        <div className="node-badge-line">
          <span>{TYPE_LABEL[node.type]}</span>
          {node.risk === "high" || node.risk === "critical" ? (
            <span className="badge risk-critical" style={{ textTransform: "uppercase", fontSize: 9 }}>
              {riskLabel(node.risk)}
            </span>
          ) : null}
        </div>
        {node.label ? (
          <div style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--text-muted)" }}>{node.label}</div>
        ) : null}
        <span className="node-addr">{shortenAddress(node.address, 8, 6)}</span>
      </div>
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </>
  );
}

const nodeTypes: NodeTypes = { entity: GraphNodeComponent };

function toFlowNodes(nodes: GraphNode[]): Node[] {
  const count = nodes.length;
  const columns = Math.ceil(Math.sqrt(count * 1.6));
  return nodes.map((n, i) => {
    const col = i % columns;
    const row = Math.floor(i / columns);
    return {
      id: n.id,
      type: "entity",
      position: { x: col * 260, y: row * 120 },
      data: n as unknown as Record<string, unknown>,
    };
  });
}

function toFlowEdges(edges: GraphEdge[]): Edge[] {
  return edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    type: "smoothstep",
    markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14 },
    label: e.asset === "ETH" ? `${e.amount} ETH` : e.asset,
    labelStyle: { fill: "var(--text-faint)" },
    className: "graph-edge",
  }));
}

export interface GraphCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  highlightedPathIds?: Set<string>;
  fitView?: boolean;
  onSelectNode?: (node: GraphNode) => void;
  onSelectEdge?: (edge: GraphEdge) => void;
  height?: string;
  testid?: string;
}

export function GraphCanvas({
  nodes,
  edges,
  highlightedPathIds,
  onSelectNode,
  onSelectEdge,
  fitView,
  height = "100%",
  testid,
}: GraphCanvasProps) {
  const flowNodes = useMemo(() => toFlowNodes(nodes), [nodes]);
  const flowEdges = useMemo(
    () =>
      toFlowEdges(edges).map((e) => ({
        ...e,
        className:
          highlightedPathIds?.has(e.id) ? "graph-edge highlighted" : "graph-edge",
      })),
    [edges, highlightedPathIds],
  );

  return (
    <div style={{ height }} data-testid={testid}>
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        fitView={fitView}
        fitViewOptions={{ padding: 0.25 }}
        minZoom={0.2}
        maxZoom={2.5}
        nodesConnectable={false}
        elementsSelectable
        proOptions={{ hideAttribution: false }}
        onNodeClick={(_, n) => {
          const data = n.data as unknown as GraphNode;
          onSelectNode?.(data);
        }}
        onEdgeClick={(_, e) => {
          const edge = edges.find((x) => x.id === e.id);
          if (edge) onSelectEdge?.(edge);
        }}
      >
        <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="rgba(139,158,190,0.14)" />
        <Controls showInteractive={false} />
        <MiniMap
          pannable
          zoomable
          nodeColor={(n) => {
            const d = n.data as unknown as GraphNode;
            const m: Record<GraphNode["type"], string> = {
              wallet: "#257fff",
              contract: "#a78bfa",
              vasp: "#2fd48b",
              unknown: "#7b8aa6",
            };
            return d.risk === "high" || d.risk === "critical" ? "#f2555a" : m[d.type];
          }}
          nodeStrokeWidth={2}
        />
      </ReactFlow>
    </div>
  );
}