import type { AttributionCandidate, InvestigationAnalysis } from "@/api/types";
import { getDemoEvidence } from "./evidence";

/**
 * SYNTHETIC ATTRIBUTION DATA — Member 3's attribution engine is not
 * implemented. These candidates use careful "candidate"/"potential
 * association" language and never claim verified ownership.
 */

export const demoCandidates: AttributionCandidate[] = [
  {
    id: "cand-1",
    wallet: "0x7c5bd5c9cde06b8c998a6a66dbdc2e9e8e2f4b13",
    vaspName: "StakingPool.io",
    confidenceLevel: "medium",
    confidenceScore: null,
    state: "candidate_detected",
    evidenceCount: 4,
    relatedAddresses: [
      "0x70819a0b1c2d3e4f5061728394a5b6c7d8e9f0a1",
      "0x819a0b1c2d3e4f5061728394a5b6c7d8e9f0a1b2",
    ],
    transactionVolume: "470,000",
    asset: "USDC",
    firstInteraction: "2026-09-06T11:05:00Z",
    lastInteraction: "2026-09-07T19:41:00Z",
    risk: "medium",
    reasoning:
      "Transactional association: repeated one-way deposits into addresses matching known StakingPool.io deposit patterns. This is a candidate association, not verified ownership.",
    factors: [
      {
        id: "f1",
        factor: "Known address intelligence",
        weight: 45,
        evidence: "2 addresses appear in curated VASP address list (needs verification)",
        source: "Curated address list (pending verification)",
        confidenceContribution: 45,
      },
      {
        id: "f2",
        factor: "Graph proximity",
        weight: 20,
        evidence: "Max 2 hops from suspect wallet via bridge contract",
        source: "Graph analysis (stub)",
        confidenceContribution: 20,
      },
      {
        id: "f3",
        factor: "Transaction pattern",
        weight: 15,
        evidence: "One-way repetitive deposit pattern, consolidation windows",
        source: "Behavioral analysis (stub)",
        confidenceContribution: 15,
      },
      {
        id: "f4",
        factor: "Temporal correlation",
        weight: null,
        evidence: "Insufficient temporal alignment data",
        source: "—",
        confidenceContribution: null,
      },
    ],
    isDemo: true,
  },
  {
    id: "cand-2",
    wallet: "0xa1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4",
    vaspName: "Proton Exchange",
    confidenceLevel: "low",
    confidenceScore: null,
    state: "evidence_insufficient",
    evidenceCount: 2,
    relatedAddresses: ["0x90a1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d"],
    transactionVolume: "1,209,000",
    asset: "ETH",
    firstInteraction: "2026-08-19T07:00:00Z",
    lastInteraction: "2026-09-09T04:12:00Z",
    risk: "high",
    reasoning:
      "Withdrawal density and phone-assisted verification patterns suggest a potential exchange association. Insufficient evidence to raise confidence.",
    factors: [
      {
        id: "f5",
        factor: "Known address intelligence",
        weight: null,
        evidence: "No curated address match",
        source: "—",
        confidenceContribution: null,
      },
      {
        id: "f6",
        factor: "Transaction behavior",
        weight: 10,
        evidence: "Exit-style withdrawals, dust-clearing behavior",
        source: "Behavioral analysis (stub)",
        confidenceContribution: 10,
      },
    ],
    isDemo: true,
  },
  {
    id: "cand-3",
    wallet: "0xdeadbeef00112233445566778899aabbccddeeff",
    vaspName: "Unknown — Mixing service signal",
    confidenceLevel: "unknown",
    confidenceScore: null,
    state: "analysis_pending",
    evidenceCount: 0,
    relatedAddresses: [],
    transactionVolume: "—",
    asset: "ETH",
    firstInteraction: null,
    lastInteraction: null,
    risk: "critical",
    reasoning:
      "Analysis pending. Flagged for churn behavior consistent with third-party mixing. No attribution engine available yet.",
    factors: [],
    isDemo: true,
  },
];

export function getDemoCandidates(): AttributionCandidate[] {
  return demoCandidates;
}

/**
 * Labeled demo result for `investigations.analyze()` when the backend is
 * unreachable (demo mode). Mirrors the live response schema so the analyzer
 * UI can be exercised offline; every record is clearly marked synthetic.
 */
export function getDemoInvestigationAnalysis(address: string): InvestigationAnalysis {
  const addr = address.trim().toLowerCase();
  return {
    address: addr,
    chain: "eth",
    transfersIngested: 30,
    graphNodes: 9,
    graphEdges: 9,
    analysisId: null,
    evidenceCount: getDemoEvidence().length,
    disclaimer:
      "This score is an analytical ranking heuristic. It is NOT proof of wallet ownership or VASP association.",
    isDemo: true,
    syntheticTransactions: true,
    intelligence: null,
    candidates: demoCandidates.map((c, i) => ({
      ...c,
      id: `demo-cand-${i}`,
      wallet: addr,
      isDemo: true,
    })),
    evidence: getDemoEvidence(),
  };
}