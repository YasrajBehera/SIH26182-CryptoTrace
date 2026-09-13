import type {
  AddressIntelligenceView,
  AttributionCandidate,
  AttributionFactor,
  AttributionState,
  BackendAddressIntelligence,
  BackendAttributionCandidate,
  BackendConfidence,
  BackendEvidenceRecord,
  BackendInvestigationResult,
  BackendScoreBreakdown,
  ConfidenceLevel,
  EvidenceItem,
  InvestigationAnalysis,
  ReliabilityLevel,
} from "./types";

/**
 * Mappers between the live investigation pipeline API
 * (POST /api/v1/investigations/{address}/analyze, GET /api/v1/evidence/...)
 * and the frontend domain models consumed by CandidateCard / EvidenceCard.
 *
 * These are pure functions and unit-tested without a network.
 */

export function toConfidenceLevel(confidence: BackendConfidence): ConfidenceLevel {
  switch (confidence) {
    case "HIGH":
      return "high";
    case "MEDIUM":
      return "medium";
    default:
      return "low";
  }
}

export function deriveCandidateState(
  confidence: BackendConfidence,
  score: number,
): AttributionState {
  if (score <= 0) return "no_attribution";
  switch (confidence) {
    case "HIGH":
      return "high_confidence";
    case "MEDIUM":
      return "medium_confidence";
    default:
      return "low_confidence";
  }
}

const FACTOR_LABELS: Record<keyof BackendScoreBreakdown, string> = {
  graph_proximity: "Graph proximity",
  known_address_match: "Known address match",
  temporal_consistency: "Temporal consistency",
  transaction_flow: "Transaction flow",
  cluster_evidence: "Cluster evidence",
};

const FACTOR_DESCRIPTIONS: Record<keyof BackendScoreBreakdown, string> = {
  graph_proximity: "Hop distance from known VASP addresses in the transaction graph.",
  known_address_match: "Direct match against the curated public VASP address directory.",
  temporal_consistency: "Regularity of transaction timing against exchange-like patterns.",
  transaction_flow: "Counterparty and in/out flow structure of the wallet.",
  cluster_evidence: "Community-cluster overlap with known VASP addresses.",
};

/** Deterministic, stable frontend id for a backend candidate (no backend id exists). */
export function candidateViewId(analysisId: string | null, index: number): string {
  const base = analysisId && analysisId.length > 12 ? analysisId.slice(0, 12) : analysisId ?? "attr";
  return `cand-${base}-${index}`;
}

export function mapBackendCandidateToView(
  candidate: BackendAttributionCandidate,
  analysisId: string | null,
  index: number,
): AttributionCandidate {
  const confidenceLevel = toConfidenceLevel(candidate.confidence);
  const state = deriveCandidateState(candidate.confidence, candidate.score);

  const factors: AttributionFactor[] = (Object.keys(FACTOR_LABELS) as Array<keyof BackendScoreBreakdown>)
    .filter((key) => (candidate.score_breakdown[key] ?? 0) > 0)
    .map((key) => {
      const contribution = Math.round(candidate.score_breakdown[key] ?? 0);
      return {
        id: `${candidateViewId(analysisId, index)}-${key}`,
        factor: FACTOR_LABELS[key],
        weight: null,
        evidence: FACTOR_DESCRIPTIONS[key],
        source: "attribution engine (back end)",
        confidenceContribution: contribution,
      };
    });

  return {
    id: candidateViewId(analysisId, index),
    wallet: candidate.address,
    vaspName: candidate.vasp_name,
    confidenceLevel,
    confidenceScore: candidate.score,
    state,
    evidenceCount: candidate.evidence_ids.length,
    relatedAddresses: [],
    transactionVolume: "—",
    asset: "",
    firstInteraction: null,
    lastInteraction: null,
    risk: "unknown",
    reasoning:
      candidate.explanation.length > 0
        ? candidate.explanation.join(" ")
        : "Candidate association identified by the attribution engine.",
    factors,
    isDemo: false,
  };
}

export function mapBackendIntelligenceToView(
  intelligence: BackendAddressIntelligence | null,
): AddressIntelligenceView | null {
  if (!intelligence) return null;
  return {
    address: intelligence.address,
    chain: intelligence.chain,
    knownVasp: intelligence.known_vasp,
    addressType: intelligence.address_type,
    entityType: intelligence.entity_type,
    jurisdiction: intelligence.jurisdiction,
    verificationStatus: intelligence.verification_status,
    confidence: intelligence.confidence,
    source: intelligence.source,
    isKnownVasp: intelligence.is_known_vasp,
    matchCount: intelligence.all_matches?.length ?? 0,
  };
}

function evidenceReliability(confidence: number): ReliabilityLevel {
  if (confidence >= 0.8) return "high";
  if (confidence >= 0.6) return "medium";
  return "low";
}

function evidenceTitle(evidenceType: EvidenceItem["type"]): string {
  return evidenceType.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function mapBackendEvidenceToItem(record: BackendEvidenceRecord): EvidenceItem {
  const synthetic = record.source === "synthetic";
  return {
    id: record.evidence_id,
    type: record.evidence_type ?? "system_observation",
    title: `${evidenceTitle(record.evidence_type)} evidence`,
    source: record.source,
    createdBy: record.provenance?.created_by ?? "unknown",
    createdAt: record.provenance?.created_at ?? new Date(0).toISOString(),
    relatedWallet: record.address ?? undefined,
    relatedTransaction: record.tx_hash ?? undefined,
    chain: record.chain ?? undefined,
    analysisId: record.attribution_id ?? undefined,
    timestamp: record.timestamp ?? null,
    reliability: evidenceReliability(record.confidence),
    notes: record.description || undefined,
    isDemo: synthetic,
  };
}

export function mapInvestigationResult(
  raw: BackendInvestigationResult,
  evidenceRecords: BackendEvidenceRecord[],
  requestedAddress: string,
  requestedChain = "eth",
): InvestigationAnalysis {
  const candidates = raw.candidates.map((c, i) =>
    mapBackendCandidateToView(c, raw.analysis_id, i),
  );

  // The pipeline reports the data source explicitly (live/demo). The ONLY
  // source of truth for whether transactions are real chain history is the
  // pipeline's `data_source` — never the number of evidence records returned
  // (evidence fetch is best-effort; a live analysis with zero evidence rows is
  // still LIVE on-chain data, not synthetic). This prevents a live run from
  // being mislabeled "SYNTHETIC DATA" merely because evidence was not linked
  // yet.
  const evidenceCount = evidenceRecords.length || raw.evidence_count;
  const syntheticTransactions = raw.data_source === "demo";
  const dataSource: "live" | "demo" = syntheticTransactions ? "demo" : "live";

  return {
    address: (raw.address ?? requestedAddress).toLowerCase(),
    chain: raw.chain ?? requestedChain,
    transfersIngested: raw.transfers_ingested,
    graphNodes: raw.graph_nodes,
    graphEdges: raw.graph_edges,
    analysisId: raw.analysis_id,
    evidenceCount,
    disclaimer: raw.disclaimer,
    isDemo: false,
    dataSource,
    syntheticTransactions,
    intelligence: mapBackendIntelligenceToView(raw.address_intelligence),
    candidates,
    evidence: evidenceRecords.map(mapBackendEvidenceToItem),
  };
}