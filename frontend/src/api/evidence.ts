import { isDemoMode } from "./config";
import { getDemoEvidence, getDemoProvenance, getDemoAuditEvents } from "@/mock";
import type { AuditEvent, EvidenceItem, ProvenanceLink } from "./types";

/** Evidence workspace contract. WAITING FOR MEMBER 3 backend. */
export const evidence = {
  async list(address?: string): Promise<EvidenceItem[]> {
    if (isDemoMode()) {
      const all = getDemoEvidence();
      if (address) return all.filter((e) => e.relatedWallet?.toLowerCase() === address.toLowerCase());
      return all;
    }
    return [];
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