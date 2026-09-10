import { isDemoMode } from "./config";
import {
  demoActivity,
  getDemoInvestigations,
  getDemoInvestigation,
  demoNotes,
  demoTimeline,
} from "@/mock";
import type {
  ActivityEvent,
  Investigation,
  InvestigationNote,
  InvestigationTimelineEvent,
} from "./types";

/**
 * Investigation management.
 *
 * The backend only exposes a legacy POST /api/v1/investigations stub today.
 * Persistence is WAITING FOR BACKEND SUPPORT; wrapped in a clean adapter so
 * Member 1 (or a later member) can swap in a real store.
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