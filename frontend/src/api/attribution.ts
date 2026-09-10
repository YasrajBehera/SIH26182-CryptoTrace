import { isDemoMode } from "./config";
import { getDemoCandidates } from "@/mock";
import { investigations } from "./investigations";
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
};