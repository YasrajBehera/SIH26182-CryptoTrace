import { isDemoMode } from "./config";
import { getDemoGraph, getDemoPath } from "@/mock";
import type { GraphPath, GraphQuery } from "./types";

/**
 * Graph frontend contract.
 *
 * WAITING FOR MEMBER 2: the Neo4j graph engine is not implemented. The
 * adapters below return clearly-labeled synthetic data. When the graph API
 * ships, replace the demo branches with client.get(...) calls and map the
 * response onto GraphNode/GraphEdge/GraphPath.
 */
export const graph = {
  async query(_query: GraphQuery) {
    if (isDemoMode()) return getDemoGraph();
    throw new Error("Graph backend (Member 2) is not implemented yet.");
  },

  async path(_from: string, _to: string): Promise<GraphPath> {
    if (isDemoMode()) return getDemoPath();
    throw new Error("Graph backend (Member 2) is not implemented yet.");
  },
};