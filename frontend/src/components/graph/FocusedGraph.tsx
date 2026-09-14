import { useMemo } from "react";
import type { GraphEdge, GraphNode } from "@/api/types";
import { shortenAddress } from "@/lib/format";

/**
 * FocusedGraph — a small, self-contained SVG "mini graph" (no @xyflow/react)
 * that shows a center entity and its immediate (depth-1) neighbours with the
 * recorded edges between them. It is intentionally read-only and small: it is
 * used for at-a-glance neighbourhood context next to the full graph.
 */

export interface FocusedGraphNode {
  node: GraphNode;
  x: number;
  y: number;
  isCenter: boolean;
}

interface FocusedGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  centerId: string;
  height?: number;
  onNodeClick?: (node: GraphNode) => void;
}

const TYPE_FILL: Record<GraphNode["type"], string> = {
  wallet: "#257fff",
  contract: "#a78bfa",
  vasp: "#2fd48b",
  unknown: "#7b8aa6",
};

const MAX_RING = 12;

export function FocusedGraph({ nodes, edges, centerId, height = 240, onNodeClick }: FocusedGraphProps) {
  const width = 340;

  const { neighbors, ringEdges } = useMemo(() => {
    const adjacent = edges.filter((e) => e.source === centerId || e.target === centerId);
    const neighborIds = new Map<string, GraphEdge[]>();
    adjacent.forEach((e) => {
      const other = e.source === centerId ? e.target : e.target === centerId ? e.source : "";
      if (!other) return;
      const list = neighborIds.get(other) ?? [];
      list.push(e);
      neighborIds.set(other, list);
    });
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const neighbors: FocusedGraphNode[] = [];
    neighborIds.forEach((_edges, id) => {
      const node = byId.get(id);
      if (!node) return;
      neighbors.push({ node, x: 0, y: 0, isCenter: false });
    });
    neighbors.sort((a, b) => a.node.address.localeCompare(b.node.address));
    const cap = neighbors.slice(0, MAX_RING);
    return { neighbors: cap, ringEdges: adjacent };
  }, [nodes, edges, centerId]);

  const ringNodes = neighbors.filter((k) => !k.isCenter);

  const layout = useMemo(() => {
    const cx = width / 2;
    const cy = height / 2;
    const radius = Math.min(width, height) / 2 - 46;
    const positions: FocusedGraphNode[] = [{ node: nodes.find((n) => n.id === centerId)!, x: cx, y: cy, isCenter: true }];
    ringNodes.forEach((entry, i) => {
      const angle = (i / Math.max(ringNodes.length, 1)) * Math.PI * 2 - Math.PI / 2;
      positions.push({ node: entry.node, x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle), isCenter: false });
    });
    return positions.filter((p) => p.node);
  }, [nodes, centerId, height, ringNodes]);

  const posById = new Map(layout.map((p) => [p.node.id, p]));

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height={height}
      style={{ display: "block", backgroundColor: "var(--surface-1)", borderRadius: 8 }}
      role="img"
      aria-label={`Focused neighbourhood graph centred on ${centerId}`}
      data-testid="focused-graph"
    >
      {ringEdges.map((e) => {
        const a = posById.get(e.source);
        const b = posById.get(e.target);
        if (!a || !b) return null;
        const dir = a.isCenter ? "out" : b.isCenter ? "in" : "both";
        return (
          <line
            key={e.id}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            stroke={dir === "in" ? "var(--text-faint)" : dir === "out" ? "#2fd48b" : "var(--text-faint)"}
            strokeWidth={1.5}
            strokeOpacity={0.7}
            markerEnd={dir === "out" ? "url(#focused-arrow)" : undefined}
          />
        );
      })}
      <defs>
        <marker id="focused-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#2fd48b" />
        </marker>
      </defs>
      {layout.map(({ node, x, y, isCenter }) => (
        <g
          key={node.id}
          onClick={onNodeClick ? () => onNodeClick(node) : undefined}
          style={onNodeClick ? { cursor: "pointer" } : undefined}
          data-testid={isCenter ? "focused-center" : "focused-neighbor"}
        >
          <circle
            cx={x}
            cy={y}
            r={isCenter ? 11 : 8}
            fill={TYPE_FILL[node.type]}
            stroke={isCenter ? "#fff" : "none"}
            strokeWidth={isCenter ? 2 : 0}
          />
          <text x={x} y={y + (isCenter ? 26 : 22)} textAnchor="middle" fontSize="10" fill="var(--text-faint)">
            {shortenAddress(node.address, 5, 4)}
          </text>
        </g>
      ))}
    </svg>
  );
}