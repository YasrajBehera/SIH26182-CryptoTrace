import { client } from "./client";
import { isDemoMode } from "./config";
import { getDemoEvidence, getDemoProvenance } from "@/mock";
import { mapBackendEvidenceToItem } from "./analysis";
import type { BackendEvidenceRecord, EvidenceItem, ProvenanceLink } from "./types";

/**
 * Evidence workspace contract.
 *
 * Live mode reads real evidence/provenance from the Member 3 evidence service:
 *   GET    /api/v1/evidence/address/{address}?chain=eth
 *   GET    /api/v1/evidence/attribution/{analysis_id}
 *   GET    /api/v1/evidence/investigation/{case_id}
 *   DELETE /api/v1/evidence/{evidence_id}
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

  async listByAnalysisId(analysisId: string): Promise<EvidenceItem[]> {
    if (isDemoMode()) {
      const all = getDemoEvidence();
      return all.slice(0, 3);
    }
    const records = await client.get<BackendEvidenceRecord[]>(
      `/api/v1/evidence/attribution/${encodeURIComponent(analysisId)}`,
      { timeoutMs: 15000 },
    );
    return records.map(mapBackendEvidenceToItem);
  },

  async listByInvestigation(caseId: string): Promise<EvidenceItem[]> {
    if (isDemoMode()) {
      const all = getDemoEvidence();
      return all.slice(0, 3);
    }
    const records = await client.get<BackendEvidenceRecord[]>(
      `/api/v1/evidence/investigation/${encodeURIComponent(caseId)}`,
      { timeoutMs: 15000 },
    );
    return records.map(mapBackendEvidenceToItem);
  },

  async delete(id: string): Promise<void> {
    if (isDemoMode()) return;
    await client.del(`/api/v1/evidence/${encodeURIComponent(id)}`);
  },

  async provenance(candidateId?: string): Promise<ProvenanceLink[]> {
    if (isDemoMode()) return getDemoProvenance();
    if (candidateId) {
      // Provenance is carried per evidence record; no separate lookup yet.
      return [];
    }
    return [];
  },
};