import { client } from "./client";
import { isDemoMode } from "./config";
import type { GlobalSearchResponse, SearchEntityType } from "./types";
import { getDemoSearchResults } from "@/mock";

/**
 * Member 8: GET /api/v1/search
 * Global search across persisted investigations, wallets, transactions,
 * evidence, analyses, curated VASPs, and reports. Falls back to labeled
 * synthetic results when the backend is unreachable.
 */
export const globalSearch = {
  async search(q: string, entityType?: SearchEntityType, limit = 20): Promise<GlobalSearchResponse> {
    if (isDemoMode()) {
      return getDemoSearchResults(q, entityType, limit);
    }
    return client.get<GlobalSearchResponse>("/api/v1/search", {
      query: { q, limit, ...(entityType ? { entity_type: entityType } : {}) },
    });
  },
};