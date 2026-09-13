import { client } from "./client";
import { isDemoMode } from "./config";
import { getDemoGraph, getDemoPath } from "@/mock";
import type { GraphEdge, GraphNode, GraphPath, GraphQuery } from "./types";

/**
 * Graph frontend contract (Member 2 Neo4j integration).
 *
 * Live mode calls the backend graph API:
 *   BFS          GET /api/v1/graph/wallets/{id}/bfs
 *   temporal     GET /api/v1/graph/wallets/{id}/temporal-flow
 *   fund-flow    GET /api/v1/graph/fund-flow
 *
 * Demo mode returns labeled synthetic data via the same shapes so the UI
 * can be exercised without Neo4j. The backend is the sole graph authority;
 * every live result is mapped verbatim (never invented) onto the shared
 * GraphNode/GraphEdge/GraphPath view models.
 */

/** Raw backend wire shapes (do not reuse in UI code). */
interface WireBfsNode {
  wallet_id?: string;
  address: string;
  chain: string;
  depth?: number;
}

interface WireBfsEdge {
  source: string;
  target: string;
  tx_id?: string;
  tx_hash?: string;
  chain?: string;
  amount?: string;
  timestamp?: number;
  block_number?: number;
}

interface WireBfsResponse {
  wallet_id: string;
  max_depth: number;
  nodes: WireBfsNode[];
  edges?: WireBfsEdge[];
}

interface WireFlowRow {
  tx_id?: string;
  tx_hash: string;
  chain?: string;
  block_timestamp?: number;
  amount: string;
  source: string;
  target: string;
}

interface WireTemporalFlowResponse {
  wallet_id: string;
  direction: string;
  flows: WireFlowRow[];
}

interface WireFundFlowTx {
  tx_hash: string;
  chain?: string;
  sender: string;
  receiver: string;
  amount: string;
  timestamp?: number;
}

interface WireFundFlowResponse {
  source: string;
  destination: string;
  wallet_path: string[];
  hop_count?: number | null;
  transactions: WireFundFlowTx[];
  found: boolean;
}

const DEFAULT_CHAIN = "eth";
const ASSET_LABEL = "ETH";

/** Neo4j namespaces wallet ids as `chain:address`. */
export function toWalletId(address: string, network?: string): string {
  const raw = (network ?? DEFAULT_CHAIN).toLowerCase();
  const chain = raw === "ethereum" || raw === "eth-mainnet" || raw === "mainnet" ? DEFAULT_CHAIN : raw;
  return `${chain}:${address.trim().toLowerCase()}`;
}

/** Convert a unix-seconds integer timestamp to ISO or null. */
function isoFromUnix(ts?: number | null): string | null {
  if (ts === undefined || ts === null) return null;
  return new Date(ts * 1000).toISOString();
}

/**
 * A graph node is identified by its full ``chain:address`` id — the same
 * namespace the backend uses for temporal-flow and BFS edges. Edge
 * ``source``/``target`` values are full ids, so node ids MUST be full ids too,
 * otherwise ReactFlow treats every edge endpoint as an orphan and the graph
 * collapses ("no meaningful nodes"). ``address`` stays the bare address for
 * display.
 */
function walletNode(nodeId: string, address?: string): GraphNode {
  const display = address ?? (nodeId.includes(":") ? (nodeId.split(":").pop() ?? nodeId) : nodeId);
  return { id: nodeId, address: display, type: "wallet", risk: "unknown", metadata: { asset: ASSET_LABEL } };
}

/** Full ``chain:address`` id for a bare address / existing backend node. */
function nodeIdOf(node: WireBfsNode): string {
  const walletId = node.wallet_id ?? "";
  if (walletId.includes(":")) return walletId.toLowerCase();
  return toWalletId(node.address ?? walletId, node.chain);
}

export interface GraphHealth {
  status: "ok" | "unavailable";
  provider: "neo4j" | "synthetic";
}

export const graph = {
  /**
   * Probe the graph engine health. In live mode this reflects whether the
   * backend reports Neo4j as reachable; otherwise the label must never claim
   * a live graph. Demo mode is always synthetic.
   */
  async health(): Promise<GraphHealth> {
    if (isDemoMode()) return { status: "unavailable", provider: "synthetic" };
    try {
      // Neo4j connect/acquire timeouts are 5s server-side; a shorter probe
      // would hose the "engine unreachable" decision on the browser side.
      const res = await client.get<{ status?: string }>("/api/v1/graph/health", { timeoutMs: 8000 });
      const ok = res.status === "ok";
      return { status: ok ? "ok" : "unavailable", provider: ok ? "neo4j" : "synthetic" };
    } catch {
      return { status: "unavailable", provider: "synthetic" };
    }
  },

  async query(query: GraphQuery): Promise<{ nodes: GraphNode[]; edges: GraphEdge[] }> {
    if (isDemoMode()) return getDemoGraph();

    const walletId = toWalletId(query.address, query.network);
    const depth = Math.min(Math.max(Number(query.depth) || 2, 1), 6);

    const [bfs, flows] = await Promise.all([
      client.get<WireBfsResponse>(`/api/v1/graph/wallets/${encodeURIComponent(walletId)}/bfs`, {
        query: { depth, max_nodes: 200, max_edges: 500 },
      }),
      client.get<WireTemporalFlowResponse>(`/api/v1/graph/wallets/${encodeURIComponent(walletId)}/temporal-flow`, {
        query: { direction: "all", max_results: 500 },
      }),
    ]);

    const nodes: GraphNode[] = [];
    const seen = new Set<string>();
    const addNode = (nodeId: string, address?: string) => {
      const id = nodeId.toLowerCase();
      if (!id || seen.has(id)) return;
      seen.add(id);
      nodes.push(walletNode(id, address));
    };

    (bfs.nodes ?? []).forEach((n) => addNode(nodeIdOf(n), n.address));
    const flowEdges = (flows.flows ?? []).map((f, i): GraphEdge => ({
      id: f.tx_id ?? `${f.tx_hash}-${i}`,
      source: f.source.toLowerCase(),
      target: f.target.toLowerCase(),
      transactionHash: f.tx_hash,
      asset: f.chain ? f.chain.toUpperCase() : ASSET_LABEL,
      amount: f.amount,
      timestamp: isoFromUnix(f.block_timestamp),
      blockNumber: null,
      direction: f.source === walletId ? "out" : f.target === walletId ? "in" : undefined,
    }));
    const bfsEdges = (bfs.edges ?? []).map((e, i): GraphEdge => ({
      id: e.tx_id ?? e.tx_hash ?? `bfs-${i}`,
      source: e.source.toLowerCase(),
      target: e.target.toLowerCase(),
      transactionHash: e.tx_hash ?? "",
      asset: e.chain ? e.chain.toUpperCase() : ASSET_LABEL,
      amount: e.amount ?? "",
      timestamp: isoFromUnix(e.timestamp),
      blockNumber: e.block_number ?? null,
    }));

    flowEdges.forEach((e) => {
      addNode(e.source);
      addNode(e.target);
    });

    const byId = new Map<string, GraphEdge>();
    [...flowEdges, ...bfsEdges].forEach((e) => byId.set(`${e.source}->${e.target}:${e.transactionHash}`, e));

    return { nodes, edges: [...byId.values()] };
  },

  async path(from: string, to: string): Promise<GraphPath> {
    if (isDemoMode()) return getDemoPath();

    const res = await client.get<WireFundFlowResponse>("/api/v1/graph/fund-flow", {
      query: { source: toWalletId(from, "eth"), target: toWalletId(to, "eth") },
    });

    const walletPath = res.wallet_path ?? [];
    const transactions = res.transactions ?? [];
    let total = 0;
    let txCount = 0;
    transactions.forEach((t) => {
      const amt = Number(t.amount);
      if (Number.isFinite(amt)) total += amt;
      txCount += 1;
    });

    return {
      nodes: walletPath.map((id) => walletNode(id)),
      edges: transactions.map((t) => ({
        id: t.tx_hash,
        source: t.sender,
        target: t.receiver,
        transactionHash: t.tx_hash,
        asset: t.chain ? t.chain.toUpperCase() : ASSET_LABEL,
        amount: t.amount,
        timestamp: isoFromUnix(t.timestamp),
        blockNumber: null,
      })),
      metrics: {
        pathLength: res.hop_count ?? Math.max(walletPath.length - 1, 0),
        transactionCount: txCount,
        totalValue: total.toLocaleString("en-US"),
        asset: ASSET_LABEL,
        timeElapsed: undefined,
        confidence: null,
      },
    };
  },
};