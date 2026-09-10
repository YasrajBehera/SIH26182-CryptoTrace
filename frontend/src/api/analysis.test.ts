import { describe, expect, it } from "vitest";
import {
  candidateViewId,
  deriveCandidateState,
  mapBackendCandidateToView,
  mapBackendEvidenceToItem,
  mapBackendIntelligenceToView,
  mapInvestigationResult,
  toConfidenceLevel,
} from "./analysis";
import type {
  BackendAttributionCandidate,
  BackendEvidenceRecord,
  BackendInvestigationResult,
} from "./types";

const candidate = (overrides: Partial<BackendAttributionCandidate> = {}): BackendAttributionCandidate => ({
  address: "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
  chain: "eth",
  vasp_name: "SynthExchange_A",
  score: 87,
  confidence: "HIGH",
  evidence_ids: ["ev-0x01", "ev-0x02", "ev-0x03"],
  score_breakdown: {
    graph_proximity: 30,
    known_address_match: 24,
    temporal_consistency: 18,
    transaction_flow: 15,
    cluster_evidence: 0,
  },
  explanation: ["Strong graph proximity to known VASP.", "Matches known-address list."],
  ...overrides,
});

const evidence = (overrides: Partial<BackendEvidenceRecord> = {}): BackendEvidenceRecord => ({
  evidence_id: "ev-0x01",
  attribution_id: "attr-0001",
  evidence_type: "graph_proximity",
  address: "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
  chain: "eth",
  tx_hash: null,
  graph_path: null,
  source: "synthetic",
  timestamp: null,
  confidence: 0.91,
  description: "Two short hops from wallet to known VASP address.",
  provenance: {
    created_at: "2026-09-10T08:00:00Z",
    created_by: "attribution_engine",
    method: "attribution_engine.flag_candidate",
    version: "0.1.0",
  },
  ...overrides,
});

const rawResult = (): BackendInvestigationResult => ({
  address: "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
  chain: "eth",
  transfers_ingested: 30,
  graph_nodes: 9,
  graph_edges: 9,
  analysis_id: "attr-0001",
  evidence_count: 3,
  disclaimer:
    "This score is an analytical ranking heuristic. It is NOT proof of wallet ownership or VASP association.",
  address_intelligence: {
    address: "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    chain: "eth",
    known_vasp: "SynthExchange_A",
    address_type: "exchange_hot_wallet",
    entity_type: "dex",
    jurisdiction: "SY",
    verification_status: "live_confirm",
    confidence: 0.93,
    source: "synthetic",
    is_known_vasp: true,
    all_matches: [
        {
          address: "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
          chain: "eth",
          vasp_name: "SynthExchange_A",
          address_type: "exchange_hot_wallet",
          source: "synthetic",
          verification_status: "verified",
          confidence: 0.93,
        },
      ],
  },
  candidates: [
    candidate({ score: 87, confidence: "HIGH" }),
    candidate({
      address: "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
      vasp_name: "SynthExchange_B",
      score: 55,
      confidence: "MEDIUM",
    }),
    candidate({
      address: "0xCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
      vasp_name: "SynthMixer_Service",
      score: 12,
      confidence: "LOW",
    }),
  ],
});

const evidenceList = (): BackendEvidenceRecord[] => [evidence()];

describe("analysis mappers (pure, no network)", () => {
  it("maps backend confidence levels to view levels", () => {
    expect(toConfidenceLevel("HIGH")).toBe("high");
    expect(toConfidenceLevel("MEDIUM")).toBe("medium");
    expect(toConfidenceLevel("LOW")).toBe("low");
  });

  it("derives candidate state from confidence and score", () => {
    expect(deriveCandidateState("HIGH", 87)).toBe("high_confidence");
    expect(deriveCandidateState("MEDIUM", 55)).toBe("medium_confidence");
    expect(deriveCandidateState("LOW", 12)).toBe("low_confidence");
    expect(deriveCandidateState("HIGH", 0)).toBe("no_attribution");
  });

  it("produces a stable frontend candidate id", () => {
    expect(candidateViewId("attr-0001", 0)).toBe("cand-attr-0001-0");
    expect(candidateViewId(null, 5)).toBe("cand-attr-5");
  });

  it("maps a backend candidate to the AttributionCandidate view model", () => {
    const mapped = mapBackendCandidateToView(rawResult().candidates[0], rawResult().analysis_id, 0);

    expect(mapped.id).toBe("cand-attr-0001-0");
    expect(mapped.wallet).toBe("0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA");
    expect(mapped.vaspName).toBe("SynthExchange_A");
    expect(mapped.confidenceLevel).toBe("high");
    expect(mapped.confidenceScore).toBe(87);
    expect(mapped.state).toBe("high_confidence");
    expect(mapped.evidenceCount).toBe(3);
    expect(mapped.risk).toBe("unknown");
    expect(mapped.isDemo).toBe(false);
    expect(mapped.reasoning).toContain("Strong graph proximity");
    expect(mapped.reasoning).toContain("Matches known-address list.");

    const graphFactor = mapped.factors.find((f) => f.factor === "Graph proximity");
    expect(graphFactor?.confidenceContribution).toBe(30);
    expect(graphFactor?.source).toBe("attribution engine (back end)");
    // Zero-contribution factor is dropped.
    expect(mapped.factors.find((f) => f.factor === "Cluster evidence")).toBeUndefined();
  });

  it("maps null intelligence to null and present intelligence to the view model", () => {
    expect(mapBackendIntelligenceToView(null)).toBeNull();

    const view = mapBackendIntelligenceToView(rawResult().address_intelligence);
    expect(view?.knownVasp).toBe("SynthExchange_A");
    expect(view?.addressType).toBe("exchange_hot_wallet");
    expect(view?.isKnownVasp).toBe(true);
    expect(view?.matchCount).toBe(1);
  });

  it("maps an evidence record to EvidenceItem with reliability bands", () => {
    const high = mapBackendEvidenceToItem(evidence({ confidence: 0.91 }));
    expect(high.reliability).toBe("high");
    expect(high.isDemo).toBe(true);
    expect(high.source).toBe("synthetic");
    expect(high.createdBy).toBe("attribution_engine");
    expect(high.createdAt).toBe("2026-09-10T08:00:00Z");
    expect(high.id).toBe("ev-0x01");
    expect(high.relatedWallet).toBe("0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA");

    expect(mapBackendEvidenceToItem(evidence({ confidence: 0.65 })).reliability).toBe("medium");
    expect(mapBackendEvidenceToItem(evidence({ confidence: 0.4 })).reliability).toBe("low");
    expect(mapBackendEvidenceToItem(evidence({ source: "etherscan" })).isDemo).toBe(false);
  });

  it("maps the full investigation result end to end", () => {
    const mapped = mapInvestigationResult(rawResult(), evidenceList(), "0xeeee", "eth");

    expect(mapped.address).toBe("0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA".toLowerCase());
    expect(mapped.chain).toBe("eth");
    expect(mapped.analysisId).toBe("attr-0001");
    expect(mapped.transfersIngested).toBe(30);
    expect(mapped.graphNodes).toBe(9);
    expect(mapped.graphEdges).toBe(9);
    expect(mapped.evidenceCount).toBe(evidenceList().length);
    expect(mapped.disclaimer).toContain("NOT proof of wallet ownership");
    expect(mapped.isDemo).toBe(false);
    expect(mapped.candidates).toHaveLength(3);
    expect(mapped.evidence).toHaveLength(1);
    expect(mapped.intelligence?.isKnownVasp).toBe(true);
  });

  it("flags synthetic transactions honestly", () => {
    const syntheticOnly = mapInvestigationResult(
      rawResult(),
      [evidence({ source: "synthetic" })],
      "0xeeee",
      "eth",
    );
    expect(syntheticOnly.syntheticTransactions).toBe(true);

    const mixed = mapInvestigationResult(
      rawResult(),
      [evidence({ source: "synthetic" }), evidence({ evidence_id: "ev-real", source: "chain" })],
      "0xeeee",
      "eth",
    );
    expect(mixed.syntheticTransactions).toBe(true);

    const real = mapInvestigationResult(rawResult(), [evidence({ source: "chain" })], "0xeeee", "eth");
    expect(real.syntheticTransactions).toBe(false);
  });
});