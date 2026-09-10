import { isDemoMode } from "./config";
import { getDemoCandidates } from "@/mock";
import type { AttributionCandidate } from "./types";

/**
 * VASP intelligence / attribution frontend contract.
 *
 * WAITING FOR MEMBER 3: the intelligence + attribution engine is not
 * implemented. The adapter returns labeled synthetic candidates. All language
 * in the UI must preserve the "candidate / potential association" nuance
 * mandated by the team (never claim verified ownership).
 */
export const attribution = {
  async candidates(address?: string): Promise<AttributionCandidate[]> {
    if (isDemoMode()) {
      const all = getDemoCandidates();
      if (address) return all.filter((c) => c.wallet.toLowerCase() === address.toLowerCase());
      return all;
    }
    return [];
  },

  async get(id: string): Promise<AttributionCandidate | null> {
    if (isDemoMode()) return getDemoCandidates().find((c) => c.id === id) ?? null;
    return null;
  },
};