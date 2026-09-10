/**
 * Shared domain contracts.
 *
 * The `BlockchainTransfer` / `WalletTransfers` shapes below are the EXACT
 * normalized schema produced by the Member 1 backend
 * (GET /api/v1/wallets/{address}/transfers). Do not change them without
 * coordinating with the backend team (see docs/API_CONTRACTS.md).
 *
 * The `Backend*` shapes mirror the live investigation pipeline API
 * (POST /api/v1/investigations/{address}/analyze) and the Member 3 evidence
 * API (GET /api/v1/evidence/...).  View models (`InvestigationAnalysis`, …)
 * are frontend-facing and are produced by the mappers in api/analysis.ts.
 */

/* ---- Member 1: blockchain ingestion (LIVE contract) ---- */

export type TransferDirection = "in" | "out";
export type TransferCategory = "external" | "internal" | "erc20" | "erc721" | "erc1155";

export interface BlockchainTransfer {
  transaction_hash: string;
  block_number: number | null;
  block_timestamp: string | null;
  from_address: string;
  to_address: string;
  value: string;
  asset: string;
  category: TransferCategory;
  direction: TransferDirection;
  raw_contract_address: string | null;
  raw_contract_value: string | null;
  chain: string;
}

export interface PaginationInfo {
  max_transfers: number;
  fetched: number;
  truncated: boolean;
}

export interface WalletTransfers {
  wallet_address: string;
  chain: string;
  transfers: BlockchainTransfer[];
  pagination: PaginationInfo;
}

export interface HealthStatus {
  status: string;
  [k: string]: unknown;
}

/* ---- Risk model (shared across modules) ---- */

export type RiskLevel = "critical" | "high" | "medium" | "low" | "unknown";

export const RISK_ORDER: RiskLevel[] = ["critical", "high", "medium", "low", "unknown"];

/* ---- Investigations (frontend-owned; hosted server-side later) ---- */

export type InvestigationStatus =
  | "draft"
  | "open"
  | "investigating"
  | "review"
  | "escalated"
  | "closed";

export interface Investigation {
  id: string;
  name: string;
  description: string;
  primaryWallet: string;
  network: string;
  risk: RiskLevel;
  status: InvestigationStatus;
  transactions: number;
  vaspCandidates: number;
  evidenceCount: number;
  assignedAnalyst: string;
  createdAt: string;
  updatedAt: string;
  tags: string[];
  isDemo?: boolean;
}

export interface InvestigationNote {
  id: string;
  author: string;
  createdAt: string;
  body: string;
}

export interface InvestigationTimelineEvent {
  id: string;
  at: string;
  actor: string;
  action: string;
  severity: "info" | "success" | "warning" | "critical";
  category?: string;
}

/* ---- Activity (dashboard) ---- */

export interface ActivityEvent {
  id: string;
  at: string;
  actor: string;
  action:
    | "wallet_investigated"
    | "transaction_imported"
    | "graph_requested"
    | "vasp_candidate"
    | "evidence_attached"
    | "risk_changed"
    | "report_generated"
    | "investigation_updated";
  caseId: string;
  caseName: string;
  severity: "info" | "success" | "warning" | "critical";
  detail?: string;
  isDemo?: boolean;
}

/* ---- Wallet analysis summary ---- */

export interface WalletSummary {
  address: string;
  network: string;
  firstSeen: string | null;
  lastActivity: string | null;
  transactionCount: number;
  incomingVolume: string;
  outgoingVolume: string;
  balance?: string | null;
  risk: RiskLevel;
  riskScore: number | null;
  investigationStatus: InvestigationStatus | "not_analyzed" | "pending";
  isDemo?: boolean;
}

/* ---- Graph (Member 2 integration contract; demo data today) ---- */

export type GraphNodeType = "wallet" | "contract" | "vasp" | "unknown";

export interface GraphNode {
  id: string;
  address: string;
  label?: string;
  type: GraphNodeType;
  risk: RiskLevel;
  metadata?: {
    asset?: string;
    volume?: string;
    txCount?: number;
  };
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  transactionHash: string;
  asset: string;
  amount: string;
  timestamp: string | null;
  direction?: TransferDirection;
}

export interface GraphPath {
  nodes: GraphNode[];
  edges: GraphEdge[];
  metrics: {
    pathLength: number;
    transactionCount: number;
    totalValue: string;
    asset: string;
    timeElapsed?: string;
    confidence: number | null;
  };
}

export interface GraphQuery {
  address: string;
  network: string;
  depth: number;
  timeRangeDays?: number | null;
}

/* ---- VASP intelligence / attribution (Member 3 integration contract) ---- */

export type ConfidenceLevel = "high" | "medium" | "low" | "unknown";
export type AttributionState =
  | "not_analyzed"
  | "analysis_pending"
  | "no_attribution"
  | "candidate_detected"
  | "evidence_insufficient"
  | "high_confidence"
  | "medium_confidence"
  | "low_confidence";

export interface AttributionFactor {
  id: string;
  factor: string;
  weight: number | null;
  evidence: string;
  source: string;
  confidenceContribution: number | null;
}

export interface AttributionCandidate {
  id: string;
  wallet: string;
  vaspName: string;
  confidenceLevel: ConfidenceLevel;
  confidenceScore: number | null;
  state: AttributionState;
  evidenceCount: number;
  relatedAddresses: string[];
  transactionVolume: string;
  asset: string;
  firstInteraction: string | null;
  lastInteraction: string | null;
  risk: RiskLevel;
  reasoning: string;
  factors: AttributionFactor[];
  isDemo?: boolean;
}

/* ---- Evidence / provenance (Member 3 integration contract) ---- */

export type EvidenceType =
  | "blockchain_transaction"
  | "address_intelligence"
  | "screenshot"
  | "document"
  | "external_source"
  | "analyst_note"
  | "system_observation"
  | "graph_proximity"
  | "known_address_match"
  | "temporal_consistency"
  | "transaction_flow"
  | "cluster_evidence";

export type ReliabilityLevel = "verified" | "high" | "medium" | "low";

export interface EvidenceItem {
  id: string;
  type: EvidenceType;
  title: string;
  source: string;
  createdBy: string;
  createdAt: string;
  relatedWallet?: string;
  relatedTransaction?: string;
  relatedCandidate?: string;
  reliability: ReliabilityLevel;
  checksum?: string;
  notes?: string;
  isDemo?: boolean;
}

export interface ProvenanceLink {
  id: string;
  label: string;
  sublabel?: string;
  kind: "candidate" | "evidence" | "transaction" | "wallet" | "source";
}

/* ---- Investigation pipeline API (LIVE backend contract, Member 3) ---- */

/** Serialized backend confidence: POST /api/v1/investigations/{address}/analyze */
export type BackendConfidence = "HIGH" | "MEDIUM" | "LOW";

export interface BackendScoreBreakdown {
  graph_proximity: number;
  known_address_match: number;
  temporal_consistency: number;
  transaction_flow: number;
  cluster_evidence: number;
}

export interface BackendAttributionCandidate {
  address: string;
  chain: string;
  vasp_name: string;
  /** Attribution score 0–100. Analytical ranking heuristic, not ownership proof. */
  score: number;
  confidence: BackendConfidence;
  evidence_ids: string[];
  score_breakdown: BackendScoreBreakdown;
  explanation: string[];
}

export interface BackendVaspMatch {
  address: string;
  chain: string;
  vasp_name: string;
  address_type: string;
  source: string;
  verification_status: "verified" | "unverified" | "disputed" | string;
  confidence: number;
}

export interface BackendAddressIntelligence {
  address: string;
  chain: string;
  known_vasp: string | null;
  address_type: string | null;
  entity_type: string | null;
  jurisdiction: string | null;
  verification_status: string | null;
  confidence: number;
  source: string | null;
  is_known_vasp: boolean;
  all_matches: BackendVaspMatch[];
}

export interface BackendEvidenceProvenance {
  created_at: string;
  created_by: string;
  method: string;
  version: string;
}

export interface BackendEvidenceRecord {
  evidence_id: string;
  attribution_id: string;
  evidence_type: EvidenceType;
  address: string;
  chain: string;
  tx_hash: string | null;
  graph_path: string[] | null;
  source: string;
  timestamp: number | null;
  /** Normalized 0–1 confidence backing this evidence record. */
  confidence: number;
  description: string;
  provenance: BackendEvidenceProvenance;
}

export interface BackendInvestigationResult {
  address: string;
  chain: string;
  transfers_ingested: number;
  graph_nodes: number;
  graph_edges: number;
  address_intelligence: BackendAddressIntelligence | null;
  candidates: BackendAttributionCandidate[];
  analysis_id: string | null;
  evidence_count: number;
  disclaimer: string;
}

/* ---- Investigation analysis view model (frontend-facing) ---- */

export interface AddressIntelligenceView {
  address: string;
  chain: string;
  knownVasp: string | null;
  addressType: string | null;
  entityType: string | null;
  jurisdiction: string | null;
  verificationStatus: string | null;
  confidence: number;
  source: string | null;
  isKnownVasp: boolean;
  matchCount: number;
}

export interface InvestigationAnalysis {
  address: string;
  chain: string;
  transfersIngested: number;
  graphNodes: number;
  graphEdges: number;
  analysisId: string | null;
  evidenceCount: number;
  disclaimer: string;
  /** True when the frontend synthesized a demo result (backend unreachable). */
  isDemo: boolean;
  /** True when the pipeline ran over synthetic transactions (backend default today). */
  syntheticTransactions: boolean;
  intelligence: AddressIntelligenceView | null;
  candidates: AttributionCandidate[];
  evidence: EvidenceItem[];
}

/* ---- Audit (roles/actions) ---- */

export type AuditAction =
  | "VIEW"
  | "CREATE"
  | "UPDATE"
  | "DELETE"
  | "EXPORT"
  | "LOGIN"
  | "LOGOUT"
  | "ANALYZE"
  | "ATTRIBUTION_REQUEST";

export interface AuditEvent {
  id: string;
  timestamp: string;
  user: string;
  action: AuditAction;
  resource: string;
  resourceId: string;
  ip?: string;
  result: "success" | "denied" | "error";
  isDemo?: boolean;
}

/* ---- Reports ---- */

export type ReportSectionKey =
  | "executive_summary"
  | "investigation_details"
  | "wallet_overview"
  | "transaction_analysis"
  | "fund_flow"
  | "graph_analysis"
  | "vasp_candidates"
  | "evidence"
  | "risk_assessment"
  | "analyst_notes"
  | "timeline"
  | "conclusion"
  | "appendix";

export interface ReportMetadata {
  caseId: string;
  caseName: string;
  investigator: string;
  generatedAt: string;
  classification: string;
  network: string;
  primaryWallet: string;
}

export interface ReportConfig {
  metadata: ReportMetadata;
  sections: ReportSectionKey[];
}

/* ---- Users / RBAC (backend auth pending; frontend contract) ---- */

export type Role = "admin" | "investigator" | "analyst" | "reviewer" | "read_only";

export interface AppUser {
  id: string;
  name: string;
  role: Role;
  title: string;
  email: string;
  lastActive?: string;
  isActive?: boolean;
}

export type Permission =
  | "investigation.read"
  | "investigation.create"
  | "investigation.update"
  | "wallet.read"
  | "wallet.analyze"
  | "graph.read"
  | "attribution.read"
  | "evidence.read"
  | "evidence.create"
  | "evidence.delete"
  | "risk.read"
  | "report.create"
  | "report.export"
  | "audit.read"
  | "user.manage"
  | "settings.manage";