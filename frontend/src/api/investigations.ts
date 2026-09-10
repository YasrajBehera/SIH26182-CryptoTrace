import { client } from "./client";
import { isDemoMode } from "./config";
import {
  demoActivity,
  getDemoInvestigations,
  getDemoInvestigation,
  demoNotes,
  demoTimeline,
  getDemoInvestigationAnalysis,
} from "@/mock";
import { mapBackendEvidenceToItem, mapInvestigationResult } from "./analysis";
import type {
  ActivityEvent,
  BackendEvidenceRecord,
  BackendInvestigationResult,
  Investigation,
  InvestigationAnalysis,
  InvestigationNote,
  InvestigationTimelineEvent,
} from "./types";

/**
 * Investigation management.
 *
 * `analyze()` drives the full live pipeline:
 *   POST /api/v1/investigations/{address}/analyze -> graph + attribution + evidence ids,
 *   GET  /api/v1/evidence/attribution/{analysis_id} -> evidence/provenance detail.
 *
 * Case persistence (list/get/create) is WAITING FOR BACKEND SUPPORT; those
 * adapters return demo data in demo mode and an empty list in live mode.
 */
export const investigations = {
  async list(): Promise<Investigation[]> {
    if (isDemoMode()) return getDemoInvestigations();
    // Live mode: no persisted investigations exist yet — return empty list.
    return [];
  },

  async get(id: string): Promise<Investigation | null> {
    if (isDemoMode()) return getDemoInvestigation(id) ?? null;
    return null;
  },

  /**
   * Run the backend investigation pipeline for a public wallet address.
   * Returns candidates ranked by attribution score plus evidence/provenance.
   */
  async analyze(address: string, chain = "eth"): Promise<InvestigationAnalysis> {
    const trimmed = address.trim().toLowerCase();

    if (isDemoMode()) {
      return getDemoInvestigationAnalysis(trimmed);
    }

    const raw = await client.post<BackendInvestigationResult>(
      `/api/v1/investigations/${encodeURIComponent(trimmed)}/analyze`,
      undefined,
      { query: { chain }, timeoutMs: 45000 },
    );

    let evidence: BackendEvidenceRecord[] = [];
    if (raw.analysis_id) {
      try {
        evidence = await client.get<BackendEvidenceRecord[]>(
          `/api/v1/evidence/attribution/${encodeURIComponent(raw.analysis_id)}`,
          { timeoutMs: 15000 },
        );
      } catch {
        // Evidence enrichment is best-effort; candidates still render.
        evidence = [];
      }
    }

    return mapInvestigationResult(raw, evidence, trimmed, chain);
  },

  /** Map backend evidence records to the frontend EvidenceItem shape. */
  mapEvidence(records: BackendEvidenceRecord[]) {
    return records.map(mapBackendEvidenceToItem);
  },

  async create(input: {
    name: string;
    description: string;
    primaryWallet: string;
    network: string;
    priority: string;
    tags: string[];
  }): Promise<Investigation> {
    if (isDemoMode()) {
      const nowStr = new Date().toISOString();
      return {
        id: `CT-2026-${String(Math.floor(100 + Math.random() * 900))}`,
        name: input.name,
        description: input.description,
        primaryWallet: input.primaryWallet,
        network: input.network,
        risk: input.priority === "critical" ? "critical" : input.priority === "high" ? "high" : input.priority === "medium" ? "medium" : "unknown",
        status: "draft",
        transactions: 0,
        vaspCandidates: 0,
        evidenceCount: 0,
        assignedAnalyst: "Unassigned",
        createdAt: nowStr,
        updatedAt: nowStr,
        tags: input.tags,
        isDemo: true,
      };
    }
    throw new Error("Investigation persistence is not implemented on the backend.");
  },

  async notes(): Promise<InvestigationNote[]> {
    return demoNotes;
  },

  async timeline(): Promise<InvestigationTimelineEvent[]> {
    return demoTimeline;
  },
};

export const activity = {
  async feed(): Promise<ActivityEvent[]> {
    if (isDemoMode()) return demoActivity;
    return [];
  },
};