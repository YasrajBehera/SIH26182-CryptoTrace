import { client, ApiError } from "./client";
import { isDemoMode } from "./config";
import {
  demoActivity,
  getDemoInvestigations,
  getDemoInvestigation,
  demoNotes,
  demoTimeline,
  getDemoInvestigationAnalysis,
  addDemoInvestigation,
} from "@/mock";
import { mapBackendEvidenceToItem, mapInvestigationResult } from "./analysis";
import type {
  ActivityEvent,
  BackendEvidenceRecord,
  BackendInvestigation,
  BackendInvestigationCreate,
  BackendInvestigationList,
  BackendInvestigationNote,
  BackendInvestigationNoteList,
  BackendInvestigationResult,
  Investigation,
  InvestigationAnalysis,
  InvestigationNote,
  InvestigationTimelineEvent,
} from "./types";

/**
 * Last-analysis context.
 *
 * Stores the most recent analysis ID so downstream pages (evidence,
 * attribution, reports) can reuse the same investigation context
 * without requiring the user to re-enter the wallet address.
 */
const LAST_ANALYSIS_KEY = "cryptotrace.lastAnalysis";

export interface LastAnalysis {
  address: string;
  chain: string;
  analysisId: string;
  at: number;
}

export function getLastAnalysis(): LastAnalysis | null {
  try {
    const raw = sessionStorage.getItem(LAST_ANALYSIS_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as LastAnalysis;
  } catch {
    return null;
  }
}

export function setLastAnalysis(ctx: Omit<LastAnalysis, "at">): void {
  try {
    sessionStorage.setItem(LAST_ANALYSIS_KEY, JSON.stringify({ ...ctx, at: Date.now() }));
  } catch {
    // sessionStorage may be unavailable (SSR, private browsing quota).
  }
}

export function networkLabel(network: string): string {
  if (!network || network.toLowerCase() === "eth" || network.toLowerCase() === "ethereum") return "Ethereum";
  return network.charAt(0).toUpperCase() + network.slice(1);
}

/** Backend InvestigationOut -> frontend Investigation view model. */
export function mapBackendInvestigationToView(b: BackendInvestigation): Investigation {
  return {
    id: b.id,
    name: b.name,
    description: b.description ?? "",
    primaryWallet: b.primary_wallet,
    network: networkLabel(b.network),
    risk: (b.risk as Investigation["risk"]) || "unknown",
    status: (b.status as Investigation["status"]) || "open",
    transactions: b.transactions ?? 0,
    vaspCandidates: b.vasp_candidates ?? 0,
    evidenceCount: b.evidence_count ?? 0,
    assignedAnalyst: b.assigned_analyst || "Unassigned",
    createdAt: b.created_at,
    updatedAt: b.updated_at,
    tags: b.tags ?? [],
    isDemo: b.is_demo,
  };
}

/**
 * Investigation management.
 *
 * `analyze()` drives the full live pipeline:
 *   POST /api/v1/investigations/{address}/analyze?case_id= -> graph + attribution + evidence ids,
 *   GET  /api/v1/evidence/attribution/{analysis_id} -> evidence/provenance detail.
 *
 * Case persistence (list/get/create) is served by the backend cases module and
 * falls back to labeled synthetic data only in demo mode.
 */
export const investigations = {
  async list(): Promise<Investigation[]> {
    if (isDemoMode()) return getDemoInvestigations();
    const res = await client.get<BackendInvestigationList>("/api/v1/investigations");
    return (res.investigations ?? []).map(mapBackendInvestigationToView);
  },

  async get(id: string): Promise<Investigation | null> {
    if (isDemoMode()) return getDemoInvestigation(id) ?? null;
    try {
      const res = await client.get<BackendInvestigation>(`/api/v1/investigations/${encodeURIComponent(id)}`);
      return mapBackendInvestigationToView(res);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) return null;
      throw err;
    }
  },

  /**
   * Run the backend investigation pipeline for a public wallet address.
   * Returns candidates ranked by attribution score plus evidence/provenance.
   * When an investigation/case id is provided it is bound to that case.
   * Stores the analysis_id in session context so downstream pages can reuse it.
   */
  async analyze(address: string, chain = "eth", caseId?: string): Promise<InvestigationAnalysis> {
    const trimmed = address.trim().toLowerCase();

    if (isDemoMode()) {
      return getDemoInvestigationAnalysis(trimmed);
    }

    const raw = await client.post<BackendInvestigationResult>(
      `/api/v1/investigations/${encodeURIComponent(trimmed)}/analyze`,
      undefined,
      { query: { chain, ...(caseId ? { case_id: caseId } : {}) }, timeoutMs: 45000 },
    );

    let evidence: BackendEvidenceRecord[] = [];
    if (raw.analysis_id) {
      setLastAnalysis({ address: trimmed, chain, analysisId: raw.analysis_id });
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
      const created: Investigation = {
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
      addDemoInvestigation(created);
      return created;
    }

    const payload: BackendInvestigationCreate = {
      name: input.name,
      description: input.description,
      primary_wallet: input.primaryWallet.trim().toLowerCase(),
      network: input.network.toLowerCase() === "ethereum" ? "eth" : input.network.toLowerCase(),
      priority: input.priority,
      tags: input.tags,
    };
    const created = await client.post<BackendInvestigation>("/api/v1/investigations", payload);
    return mapBackendInvestigationToView(created);
  },

  async notes(caseId: string): Promise<InvestigationNote[]> {
    if (isDemoMode()) return demoNotes;
    const res = await client.get<BackendInvestigationNoteList>(
      `/api/v1/investigations/${encodeURIComponent(caseId)}/notes`,
    );
    return (res.notes ?? []).map((n) => ({
      id: n.id,
      author: n.author,
      createdAt: n.created_at,
      body: n.body,
    }));
  },

  /**
   * Persist an analyst note on a case. In demo mode the note is appended to
   * the labeled synthetic set so the page behaves end-to-end without a backend.
   */
  async addNote(caseId: string, body: string, author: string): Promise<InvestigationNote> {
    if (isDemoMode()) {
      const note: InvestigationNote = {
        id: `n-${Date.now()}`,
        author,
        createdAt: new Date().toISOString(),
        body,
      };
      demoNotes.push(note);
      return note;
    }
    const created = await client.post<BackendInvestigationNote>(
      `/api/v1/investigations/${encodeURIComponent(caseId)}/notes`,
      { body, author },
    );
    return {
      id: created.id,
      author: created.author,
      createdAt: created.created_at,
      body: created.body,
    };
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