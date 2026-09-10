import { client } from "./client";
import { isDemoMode } from "./config";
import { getDemoEvidence, getDemoProvenance, getDemoAuditEvents } from "@/mock";
import { mapBackendEvidenceToItem } from "./analysis";
import type { AuditEvent, BackendEvidenceRecord, EvidenceItem, ProvenanceLink } from "./types";

/**
 * Evidence workspace contract.
 *
 * Live mode reads real evidence/provenance from the Member 3 evidence service:
 *   GET /api/v1/evidence/address/{address}?chain=eth
 */
export const evidence = {
  async list(address?: string): Promise<EvidenceItem[]> {
    if (isDemoMode()) {
      const all = getDemoEvidence();
      if (address) return all.filter((e) => e.relatedWallet?.toLowerCase() === address.toLowerCase());
      return all;
    }
    if (!address) return [];
    const records = await client.get<BackendEvidenceRecord[]>(
      `/api/v1/evidence/address/${encodeURIComponent(address.trim().toLowerCase())}`,
      { query: { chain: "eth" } },
    );
    return records.map(mapBackendEvidenceToItem);
  },

  async delete(_id: string): Promise<void> {
    if (isDemoMode()) return;
    throw new Error("Evidence deletion requires the Member 3 evidence service.");
  },

  async provenance(candidateId?: string): Promise<ProvenanceLink[]> {
    if (isDemoMode()) return getDemoProvenance();
    if (candidateId) {
      // Future backend lookup
      return [];
    }
    return [];
  },
};

/** Audit log contract. WAITING FOR BACKEND auth/audit support. */
export const audit = {
  async list(): Promise<AuditEvent[]> {
    if (isDemoMode()) return getDemoAuditEvents();
    return [];
  },
};