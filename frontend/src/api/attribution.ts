import { isDemoMode } from "./config";
import { getDemoCandidates, getDemoVaspNames } from "@/mock";
import { investigations } from "./investigations";
import { mapBackendIntelligenceToView } from "./analysis";
import { client } from "./client";
import type {
  AddressIntelligenceView,
  AttributionCandidate,
  BackendAddressIntelligence,
} from "./types";

/**
 * VASP intelligence / attribution frontend contract.
 *
 * Live mode runs the backend investigation pipeline
 * (POST /api/v1/investigations/{address}/analyze) and maps its ranked
 * candidates onto the shared AttributionCandidate shape. All language in the
 * UI must preserve the "candidate / potential association" nuance mandated by
 * the team (never claim verified ownership).
 */
export const attribution = {
  async candidates(address?: string): Promise<AttributionCandidate[]> {
    if (isDemoMode()) {
      const all = getDemoCandidates();
      if (address) return all.filter((c) => c.wallet.toLowerCase() === address.toLowerCase());
      return all;
    }
    if (!address) return [];
    const analysis = await investigations.analyze(address);
    return analysis.candidates;
  },

  async get(id: string): Promise<AttributionCandidate | null> {
    if (isDemoMode()) return getDemoCandidates().find((c) => c.id === id) ?? null;
    return null;
  },

  /**
   * Direct known-address directory lookup for a single wallet. Distinct from
   * the behavioral/graph candidate ranking: this answers "is this exact
   * address listed in the curated VASP directory?" using the cheap
   * GET /api/v1/intelligence/address/{address} endpoint (no analysis pipeline,
   * no blockchain fetch). Null when the wallet has no direct directory match.
   */
  async intelligence(address: string): Promise<AddressIntelligenceView | null> {
    if (isDemoMode()) return null;
    // Not a known VASP in the demo directory either — mirror live shape.
    try {
      const raw = await client.get<BackendAddressIntelligence>(
        `/api/v1/intelligence/address/${encodeURIComponent(address)}`,
        { query: { chain: "eth", data_source: "live" }, timeoutMs: 8000 },
      );
      return mapBackendIntelligenceToView(raw);
    } catch {
      return null;
    }
  },

  /**
   * Known VASP entity names for global search.
   * Live: GET /api/v1/intelligence/vasp/names (curated directory).
   * Demo: labeled synthetic directory.
   * Never throws — search degrades to an empty list on failure.
   */
  async vaspNames(): Promise<string[]> {
    if (isDemoMode()) return getDemoVaspNames();
    try {
      const res = await client.get<{ chain: string; vasp_names: string[] }>("/api/v1/intelligence/vasp/names", {
        query: { chain: "eth" },
        timeoutMs: 8000,
      });
      return res.vasp_names ?? [];
    } catch {
      return [];
    }
  },
};