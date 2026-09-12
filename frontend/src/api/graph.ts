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

interface WireBfsResponse {
  wallet_id: string;
  max_depth: number;
  nodes: WireBfsNode[];
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

function walletNode(address: string): GraphNode {
  return { id: address, address, type: "wallet", risk: "unknown", metadata: { asset: ASSET_LABEL } };
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
      const res = await client.get<{ status?: string }>("/api/v1/graph/health", { timeoutMs: 4000 });
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
        query: { depth, max_nodes: 200 },
      }),
      client.get<WireTemporalFlowResponse>(`/api/v1/graph/wallets/${encodeURIComponent(walletId)}/temporal-flow`, {
        query: { direction: "all", max_results: 500 },
      }),
    ]);

    const nodes: GraphNode[] = [];
    const seen = new Set<string>();
    const addNode = (address: string) => {
      if (!address || seen.has(address)) return;
      seen.add(address);
      nodes.push(walletNode(address));
    };

    (bfs.nodes ?? []).forEach((n) => addNode((n.address ?? n.wallet_id ?? "").toLowerCase()));
    (flows.flows ?? []).forEach((f) => {
      addNode(f.source.toLowerCase());
      addNode(f.target.toLowerCase());
    });

    const edges: GraphEdge[] = (flows.flows ?? []).map((f, i) => ({
      id: f.tx_id ?? `${f.tx_hash}-${i}`,
      source: f.source,
      target: f.target,
      transactionHash: f.tx_hash,
      asset: f.chain ? f.chain.toUpperCase() : ASSET_LABEL,
      amount: f.amount,
      timestamp: isoFromUnix(f.block_timestamp),
    }));

    return { nodes, edges };
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
      nodes: walletPath.map((address) => walletNode(address.toLowerCase())),
      edges: transactions.map((t) => ({
        id: t.tx_hash,
        source: t.sender,
        target: t.receiver,
        transactionHash: t.tx_hash,
        asset: t.chain ? t.chain.toUpperCase() : ASSET_LABEL,
        amount: t.amount,
        timestamp: isoFromUnix(t.timestamp),
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