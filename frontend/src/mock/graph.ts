import type { GraphEdge, GraphNode, GraphPath } from "@/api/types";

/**
 * SYNTHETIC GRAPH DATA — Member 2's Neo4j engine is not implemented.
 * This demo graph illustrates the frontend integration contract only.
 */

type NodeSpec = [id: string, address: string, label: string | undefined, type: GraphNode["type"], risk: GraphNode["risk"]];

const NODES: NodeSpec[] = [
  ["n0", "0x7c5bd5c9cde06b8c998a6a66dbdc2e9e8e2f4b13", undefined, "wallet", "high"],
  ["n1", "0xdeadbeef00112233445566778899aabbccddeeff", "Deposit Wallet (suspect)", "wallet", "critical"],
  ["n2", "0x3c9a2f4e1d5b6a7c8d9e0f1a2b3c4d5e6f7a8b9c", "Intermediate", "wallet", "medium"],
  ["n3", "0x1a2b3c4d5e6f70819a0b1c2d3e4f5061728394a5b", "Token Router", "contract", "low"],
  ["n4", "0x4d5e6f70819a0b1c2d3e4f5061728394a5b6c7d8", "Swap Pair", "contract", "low"],
  ["n5", "0x5e6f70819a0b1c2d3e4f5061728394a5b6c7d8e9", "Bridge Contract", "contract", "medium"],
  ["n6", "0x6f70819a0b1c2d3e4f5061728394a5b6c7d8e9f0", "OTC Counterparty", "wallet", "high"],
  ["n7", "0x70819a0b1c2d3e4f5061728394a5b6c7d8e9f0a1", "StakingPool.io (candidate)", "vasp", "medium"],
  ["n8", "0x819a0b1c2d3e4f5061728394a5b6c7d8e9f0a1b2", "Unknown Entity", "unknown", "unknown"],
];

const EDGES: Array<[string, string, string, string, string, string | null]> = [
  ["n0", "n1", "0xe1", "USDT", "1250000", "2026-09-02T18:31:00Z"],
  ["n0", "n2", "0xe2", "USDT", "310000", "2026-09-03T09:12:00Z"],
  ["n1", "n3", "0xe3", "USDT", "820000", "2026-09-04T22:04:00Z"],
  ["n3", "n4", "0xe4", "ETH", "12.5", "2026-09-04T22:05:00Z"],
  ["n4", "n6", "0xe5", "USDC", "430000", "2026-09-05T01:48:00Z"],
  ["n2", "n5", "0xe6", "ETH", "88", "2026-09-05T14:22:00Z"],
  ["n5", "n7", "0xe7", "USDC", "290000", "2026-09-06T11:05:00Z"],
  ["n2", "n8", "0xe8", "DAI", "41000", "2026-09-07T03:33:00Z"],
  ["n6", "n7", "0xe9", "USDC", "180000", "2026-09-07T19:41:00Z"],
];

function specToNode([id, address, label, type, risk]: NodeSpec): GraphNode {
  return { id, address, label, type, risk, metadata: { txCount: 0 } };
}

export function getDemoGraph(): { nodes: GraphNode[]; edges: GraphEdge[] } {
  return {
    nodes: NODES.map(specToNode),
    edges: EDGES.map(([source, target, hash, asset, amount, timestamp], i) => ({
      id: `k${i}`,
      source,
      target,
      transactionHash: `${hash}${"0".repeat(58)}`.padEnd(64, "f"),
      asset,
      amount,
      timestamp,
    })),
  };
}

export function getDemoPath(): GraphPath {
  const { nodes, edges } = getDemoGraph();
  const pathNodeIds = ["n0", "n1", "n3", "n4", "n6", "n7"];
  const pathEdgeIds = ["k0", "k2", "k3", "k4", "k8"];
  return {
    nodes: nodes.filter((n) => pathNodeIds.includes(n.id)),
    edges: edges.filter((e) => pathEdgeIds.includes(e.id)),
    metrics: {
      pathLength: 5,
      transactionCount: 5,
      totalValue: "1,630,000",
      asset: "USDT/USDC",
      timeElapsed: "4 days, 2 hours",
      confidence: null,
    },
  };
}