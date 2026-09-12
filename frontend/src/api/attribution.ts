import { isDemoMode } from "./config";
import { getDemoCandidates, getDemoVaspNames } from "@/mock";
import { investigations } from "./investigations";
import { client } from "./client";
import type { AttributionCandidate } from "./types";

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