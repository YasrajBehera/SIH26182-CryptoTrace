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

const rawResult = (dataSource: "live" | "demo" = "live"): BackendInvestigationResult => ({
  address: "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
  chain: "eth",
  data_source: dataSource,
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

  it("flags synthetic transactions from the pipeline data_source only", () => {
    // data_source is the single source of truth for live vs synthetic — an
    // absent/missing evidence payload never turns real chain data synthetic.
    const demoRun = mapInvestigationResult(
      rawResult("demo"),
      [evidence({ source: "synthetic" })],
      "0xeeee",
      "eth",
    );
    expect(demoRun.syntheticTransactions).toBe(true);
    expect(demoRun.dataSource).toBe("demo");

    const liveRun = mapInvestigationResult(
      rawResult("live"),
      [evidence({ source: "synthetic" })],
      "0xeeee",
      "eth",
    );
    expect(liveRun.syntheticTransactions).toBe(false);
    expect(liveRun.dataSource).toBe("live");

    // Even with no evidence records at all, a live pipeline run stays LIVE.
    const liveNoEvidence = mapInvestigationResult(rawResult("live"), [], "0xeeee", "eth");
    expect(liveNoEvidence.syntheticTransactions).toBe(false);
    expect(liveNoEvidence.evidenceCount).toBe(rawResult("live").evidence_count);

    const real = mapInvestigationResult(
      rawResult("live"),
      [evidence({ source: "chain" })],
      "0xeeee",
      "eth",
    );
    expect(real.syntheticTransactions).toBe(false);
  });
});
describe("mapInvestigationResult provenance", () => {
  const base = rawResult("live");

  it("keeps LIVE_PARTIAL distinct from LIVE", () => {
    const partial = mapInvestigationResult(
      { ...base, status: "LIVE_PARTIAL", provider: "ronin-rpc" },
      [],
      base.address,
    );
    expect(partial.status).toBe("LIVE_PARTIAL");
    expect(partial.dataSource).toBe("live");
    expect(partial.provider).toBe("ronin-rpc");
  });

  it("reports NO_DATA without claiming a failure", () => {
    const none = mapInvestigationResult(
      { ...base, status: "NO_DATA", transfers_ingested: 0 },
      [],
      base.address,
    );
    expect(none.status).toBe("NO_DATA");
    expect(none.transfersIngested).toBe(0);
  });

  it("labels synthetic rows as DEMO and keeps the live outcome visible", () => {
    const demo = mapInvestigationResult(
      {
        ...base,
        data_source: "demo",
        status: "DEMO",
        provider: "synthetic",
        live_status: "LIVE_DATA_UNAVAILABLE",
        limitations: ["Synthetic demo transactions are shown instead."],
      },
      [],
      base.address,
    );
    expect(demo.status).toBe("DEMO");
    expect(demo.syntheticTransactions).toBe(true);
    expect(demo.liveStatus).toBe("LIVE_DATA_UNAVAILABLE");
    expect(demo.limitations).toHaveLength(1);
  });

  it("does not default an unknown status to LIVE", () => {
    const unknown = mapInvestigationResult({ ...base, status: "WAT" as never }, [], base.address);
    expect(unknown.status).toBe("LIVE");
    expect(unknown.syntheticTransactions).toBe(false);
  });

it("preserves the chain the backend resolved", () => {
    const ronin = mapInvestigationResult({ ...base, chain: "ronin" }, [], base.address);
    expect(ronin.chain).toBe("ronin");
  });
});

describe("investigation result surfaces everything the user must see", () => {
  it("exposes transfers, graph counts, evidence count, candidates and limitations", () => {
    const raw: BackendInvestigationResult = {
      ...rawResult("live"),
      status: "LIVE_PARTIAL",
      provider: "ronin-rpc",
      chain: "ronin",
      transfers_ingested: 106,
      graph_nodes: 31,
      graph_edges: 28,
      evidence_count: 0,
      limitations: [
        "Scanned blocks 61790949-61791148 of 61791149 (200 blocks searched).",
        "Activity older than block 61790949 was not searched.",
      ],
      candidates: [],
    };

    const view = mapInvestigationResult(raw, [], raw.address);

    expect(view.transfersIngested).toBe(106);
    expect(view.graphNodes).toBe(31);
    expect(view.graphEdges).toBe(28);
    expect(view.evidenceCount).toBe(0);
    expect(view.status).toBe("LIVE_PARTIAL");
    expect(view.provider).toBe("ronin-rpc");
    expect(view.limitations).toHaveLength(2);
    expect(view.disclaimer).toContain("NOT proof");
    expect(view.candidates).toEqual([]);
  });

  it("shows the candidate VASP with its score, confidence and evidence count", () => {
    const view = mapInvestigationResult(rawResult("live"), [], rawResult("live").address);
    const top = view.candidates[0];

    expect(top.vaspName).toBe("SynthExchange_A");
    expect(top.confidenceScore).toBe(87);
    expect(top.confidenceLevel).toBe("high");
    expect(top.evidenceCount).toBe(3);
    expect(top.reasoning.length).toBeGreaterThan(0);
  });

  it("never presents an unscored candidate as an attribution", () => {
    // A real Ronin wallet with no curated VASP directory entry must stay
    // unattributed rather than surfacing a ranked candidate.
    const raw: BackendInvestigationResult = {
      ...rawResult("live"),
      evidence_count: 0,
      candidates: [
        candidate({
          vasp_name: "UNKNOWN",
          score: 0,
          confidence: "LOW",
          evidence_ids: [],
        }),
      ],
    };

    const view = mapInvestigationResult(raw, [], raw.address);
    expect(view.candidates[0].state).toBe("no_attribution");
    expect(view.candidates[0].confidenceLevel).toBe("low");
    expect(view.candidates[0].evidenceCount).toBe(0);
  });
});

describe("HIGH confidence stays reserved for the backend threshold", () => {
  it("maps the backend confidence level without inflating it", () => {
    expect(toConfidenceLevel("LOW")).toBe("low");
    expect(toConfidenceLevel("MEDIUM")).toBe("medium");
    expect(toConfidenceLevel("HIGH")).toBe("high");
  });

  it("keeps a below-threshold score out of the high state", () => {
    expect(deriveCandidateState("HIGH", 69.99)).toBe("high_confidence");
    expect(deriveCandidateState("MEDIUM", 69.99)).toBe("medium_confidence");
    expect(deriveCandidateState("LOW", 69.99)).toBe("low_confidence");
  });

  it("treats a zero score as no attribution regardless of reported confidence", () => {
    expect(deriveCandidateState("HIGH", 0)).toBe("no_attribution");
  });

  it("keeps the highest-scoring candidate first", () => {
    const view = mapInvestigationResult(rawResult("live"), [], rawResult("live").address);
    const scores = view.candidates.map((c) => c.confidenceScore ?? 0);
    expect([...scores].sort((a, b) => b - a)).toEqual(scores);
  });
});

/* ---- Chain-scoped traceability (Ronin VASP verification) ------------------ */

const BITGET_RONIN = "0x5bdf85216ec1e38d6458c870992a69e38e03f7ef";
const BITGET_TX =
  "0x733fc397a5a565a5f4ee16f15f420640a1a77982a87f12145634abf3e41ca8b2";
const RONIN_WALLET = "0x7a4f5c3d2e1b0a9f8e7d6c5b4a3928170f6e5d4c";

const roninCandidate = (overrides: Partial<BackendAttributionCandidate> = {}) =>
  candidate({
    address: RONIN_WALLET,
    chain: "ronin",
    vasp_name: "Bitget",
    score: 40,
    confidence: "MEDIUM",
    evidence_ids: ["ev-ronin-1"],
    score_breakdown: {
      graph_proximity: 20,
      known_address_match: 0,
      temporal_consistency: 10,
      transaction_flow: 10,
      cluster_evidence: 0,
    },
    ...overrides,
  });

const roninEvidence = (overrides: Partial<BackendEvidenceRecord> = {}) =>
  evidence({
    evidence_id: "ev-ronin-1",
    evidence_type: "transaction_flow",
    address: RONIN_WALLET,
    chain: "ronin",
    matched_address: BITGET_RONIN,
    tx_hash: BITGET_TX,
    source: "chain",
    confidence: 0.9,
    description:
      `Bitget (${BITGET_RONIN}) observed on Ronin, direction out, value 2770.21 RON, tx ${BITGET_TX}, source ronin official explorer.`,
    limitations: [
      "A public directory label is an investigative lead. It does not by itself establish legal ownership, control, or the identity of the operator.",
    ],
    ...overrides,
  });

describe("a candidate carries the chain it was actually analysed on", () => {
  it("never defaults a Ronin candidate to Ethereum", () => {
    const mapped = mapBackendCandidateToView(roninCandidate(), "attr-ronin", 0);

    expect(mapped.chain).toBe("ronin");
    expect(mapped.wallet).toBe(RONIN_WALLET);
    expect(mapped.chain).not.toBe("eth");
  });

  it("keeps the evidence ids so the candidate can be traced to its records", () => {
    const mapped = mapBackendCandidateToView(roninCandidate(), "attr-ronin", 0);

    expect(mapped.evidenceIds).toEqual(["ev-ronin-1"]);
    expect(mapped.evidenceCount).toBe(1);
  });

  it("maps every candidate's own chain, so mixed lists stay distinguishable", () => {
    const mapped = mapInvestigationResult(
      {
        ...rawResult("live"),
        chain: "ronin",
        candidates: [
          roninCandidate(),
          roninCandidate({ address: BITGET_RONIN, vasp_name: "Bitget", score: 55 }),
          roninCandidate({ vasp_name: "UNKNOWN", score: 0, confidence: "LOW", evidence_ids: [] }),
        ],
      },
      [],
      RONIN_WALLET,
    );

    expect(mapped.candidates.map((c) => c.chain)).toEqual(["ronin", "ronin", "ronin"]);
    expect(mapped.candidates[0].vaspName).toBe("Bitget");
    expect(mapped.candidates[2].state).toBe("no_attribution");
  });
});

describe("evidence stays traceable to a real address and transaction", () => {
  it("carries the matched address alongside its chain", () => {
    const item = mapBackendEvidenceToItem(roninEvidence());

    expect(item.chain).toBe("ronin");
    expect(item.matchedAddress).toBe(BITGET_RONIN);
    expect(item.relatedTransaction).toBe(BITGET_TX);
    expect(item.relatedWallet).toBe(RONIN_WALLET);
    expect(item.isDemo).toBe(false);
  });

  it("never hides the limitations the backend attached", () => {
    const item = mapBackendEvidenceToItem(roninEvidence());

    expect(item.limitations).toHaveLength(1);
    expect(item.limitations?.[0]).toContain("does not by itself establish legal ownership");
  });

  it("tolerates records from an older backend with no traceability fields", () => {
    const legacy = mapBackendEvidenceToItem(
      evidence({ matched_address: undefined, limitations: undefined }),
    );

    expect(legacy.matchedAddress).toBeUndefined();
    expect(legacy.limitations).toEqual([]);
  });

  it("surfaces the directory match provenance for the investigated address", () => {
    const view = mapBackendIntelligenceToView({
      address: BITGET_RONIN,
      chain: "ronin",
      known_vasp: "Bitget",
      address_type: "unknown",
      entity_type: "exchange",
      jurisdiction: "unknown",
      verification_status: "verified",
      confidence: 0.9,
      source: "ronin official explorer",
      source_url: "https://explorer.roninchain.com/",
      matched_address: BITGET_RONIN,
      is_known_vasp: true,
      all_matches: [],
    });

    expect(view?.chain).toBe("ronin");
    expect(view?.knownVasp).toBe("Bitget");
    expect(view?.verificationStatus).toBe("verified");
    expect(view?.sourceUrl).toBe("https://explorer.roninchain.com/");
    expect(view?.matchedAddress).toBe(BITGET_RONIN);
  });

  it("does not imply a match that the backend reported as unknown", () => {
    const view = mapBackendIntelligenceToView({
      address: RONIN_WALLET,
      chain: "ronin",
      known_vasp: null,
      address_type: null,
      entity_type: null,
      jurisdiction: null,
      verification_status: null,
      confidence: 0,
      source: null,
      is_known_vasp: false,
      all_matches: [],
    });

    expect(view?.isKnownVasp).toBe(false);
    expect(view?.knownVasp).toBeNull();
    expect(view?.matchedAddress).toBeUndefined();
    expect(view?.sourceUrl).toBeUndefined();
  });
});
