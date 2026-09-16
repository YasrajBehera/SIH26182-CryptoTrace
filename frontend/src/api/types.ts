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
  /** Offset into the sorted set held by the backend (server-side pagination). */
  offset?: number;
  /** Page size requested (server-side pagination). */
  limit?: number | null;
  /** Total normalized transfers held for the wallet. */
  total?: number;
  has_next?: boolean;
  has_previous?: boolean;
  /** "provider" = fetched fresh from the blockchain provider; "database" = served from persisted PostgreSQL. */
  source?: "provider" | "database";
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
  /** Unique transactions persisted in the wallet store (may differ from the
   *  latest analysis batch due to on-chain de-duplication). */
  persistedTransactions?: number;
  vaspCandidates: number;
  evidenceCount: number;
  assignedAnalyst: string;
  createdAt: string;
  updatedAt: string;
  tags: string[];
  /** SEPARATE curated sanctions/illicit intelligence block. Absent (undefined)
   *  means UNKNOWN / NOT ASSESSED — never "not criminal". This block never
   *  modifies the analytical risk fields above. */
  criminalIntelligence?: CriminalIntelligence;
  isDemo?: boolean;
}

/* ---- Backend investigation contracts (cases module) ---- */

export interface BackendInvestigationCreate {
  name: string;
  description: string;
  primary_wallet: string;
  network: string;
  priority: string;
  tags: string[];
}

export interface BackendInvestigation {
  id: string;
  name: string;
  description: string;
  primary_wallet: string;
  network: string;
  priority: string;
  risk: string;
  status: string;
  transactions: number;
  persisted_transactions: number;
  vasp_candidates: number;
  evidence_count: number;
  assigned_analyst: string;
  created_by: number;
  latest_analysis_id: string | null;
  data_source: string;
  created_at: string;
  updated_at: string;
  tags: string[];
  is_demo: boolean;
}

export interface BackendInvestigationList {
  investigations: BackendInvestigation[];
  total: number;
  source: string;
}

export interface MLRiskAssessment {
  status: "trained" | "not_trained" | "unavailable";
  probability: number | null;
  label: string;
  level: string;
  threshold: number | null;
  required_features: string[];
  missing_features: string[];
  top_features: Array<{ feature: string; gain: number }>;
  model_version: string | null;
  dataset_version: string | null;
  explanation: string;
  wording: string;
  disclaimer: string;
}

export interface BackendRiskAssessment {
  investigation_id: string | null;
  wallet_address: string;
  chain: string;
  level: RiskLevel;
  risk_score: number;
  summary: string;
  reasoning: string[];
  factors: Array<{ label: string; detail: string; weight: number }>;
  data_source: string;
  disclaimer: string;
  created_at: string;
  criminal_intelligence?: Record<string, unknown> | null;
  ml_assessment?: MLRiskAssessment | null;
}

export interface InvestigationNote {
  id: string;
  author: string;
  createdAt: string;
  body: string;
}

/** Raw backend wire shapes: GET/POST /api/v1/investigations/{id}/notes. */
export interface BackendInvestigationNote {
  id: string;
  case_id: string;
  author: string;
  body: string;
  created_at: string;
}

export interface BackendInvestigationNoteList {
  notes: BackendInvestigationNote[];
  total: number;
  case_id: string;
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

/* ---- Graph (backend graph API over the Neo4j engine) ---- */

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
  /** Block number of the recorded transfer; null when the engine did not expose it. */
  blockNumber: number | null;
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

/* ---- Criminal / Sanctions Intelligence (curated public intelligence) ---- *
 * This layer is SEPARATE from VASP attribution. Only an EXACT address match
 * against the curated public sanctions/illicit directory elevates
 * CriminalIntelligence.level to "high". No neighbor is ever flagged and the
 * analytical risk score is never modified by this block. */

export interface SanctionsIntelligenceRecord {
  record_id: string;
  chain: string;
  address: string;
  entity: string;
  classification: "sanctioned" | "illicit" | string;
  source: string;
  match_type: "exact_address" | string;
  confidence: string;
  source_type: string;
  reference?: string | null;
  notes?: string;
  created_at?: string;
}

export interface SanctionsLookup {
  address: string;
  chain: string;
  matched: boolean;
  level: "high" | "unknown" | string;
  data_source: string;
  record: SanctionsIntelligenceRecord | null;
}

export interface CriminalIntelligence {
  level: string;
  status: string;
  reason?: string;
  entity?: string;
  source?: string;
  source_type?: string;
  match_type?: string;
  confidence?: string;
  provenance_source_type?: string;
  evidence_id?: string;
  signals?: string[];
  disclaimer?: string;
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
  /** Chain the evidence was recorded against (backend EvidenceRecord.chain). */
  chain?: string;
  /** Attribution/analysis id that generated the record. */
  analysisId?: string;
  /** Optionalevidence-native unix timestamp, when the record carries one. */
  timestamp?: number | null;
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
  investigation_id?: string | null;
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
  case_id?: string | null;
  data_source?: string;
}

/** GET /api/v1/investigations/{id}/context — persisted investigation context. */
export interface BackendInvestigationContext {
  case: BackendInvestigation;
  wallet_summary: Record<string, unknown> | null;
  latest_analysis: {
    analysis_id: string;
    data_source: string;
    candidate_count: number;
    transaction_count: number;
    /** Persisted candidate payload from the most recent attached analysis. */
    candidates: BackendAttributionCandidate[];
  } | null;
  evidence: BackendEvidenceRecord[];
  risk: BackendRiskAssessment | null;
  reports: string[];
  scope: string;
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
  /** The pipeline's explicit data source: "live" (real chain) or "demo" (synthetic). */
  dataSource: "live" | "demo";
  /** True when the pipeline ran over synthetic transactions (data_source === "demo"). */
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
  | "ATTRIBUTION_REQUEST"
  | "SEARCH"
  | "CASE_CONTEXT";

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
  | "criminal_sanctions_intelligence"
  | "evidence"
  | "risk_assessment"
  | "analyst_notes"
  | "timeline"
  | "conclusion"
  | "appendix";

export interface ReportMetadata {
  /** Persisted investigation id the report is scoped to. Null when no case is
   *  linked — the backend then renders context sections as UNAVAILABLE. The UI
   *  must not fabricate a synthetic id here (see ReportsPage). */
  caseId: string | null;
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

/* ---- SAHYOG referral intake (DEMO flow; backend adapter) ---- */

export interface SahyogReferralView {
  id: string;
  firNo: string;
  reportedAt: string;
  victimName: string;
  amountUSDT: number;
  suspectWallet: string;
  chain: "eth" | "btc";
  status: "new" | "triaged" | "handed_off";
  triage?: {
    risk: "high" | "medium" | "low";
    walletAgeMonths: number;
    exchangeExposed: boolean;
    priorFlags: number;
    recommendation: "investigate" | "monitor" | "watchlist";
    triagedBy: string;
    triagedAt: string;
  };
  handoffCaseId?: string;
}

export interface SahyogBackendOut {
  id: string;
  fir_no: string;
  reported_at: string | null;
  victim_name: string;
  amount_usdt: number;
  suspect_wallet: string;
  chain: string;
  status: string;
  triage: Record<string, unknown> | null;
  handoff_case_id: string | null;
  data_source: string;
}

export interface SahyogCreateInput {
  firNo: string;
  victimName: string;
  amountUSDT: number;
  suspectWallet: string;
  chain: "eth" | "btc";
}

/* ---- Users / RBAC (backend auth pending; frontend contract) ---- */

export type Role = "admin" | "senior_investigator" | "investigator" | "analyst" | "reviewer" | "read_only";

export interface AppUser {
  id: string;
  username: string;
  name: string;
  role: Role;
  title: string;
  email: string;
  lastActive?: string;
  isActive?: boolean;
}

export type Permission =
  | "search.read"
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

/* ---- Global Search ---- */

export type SearchEntityType =
  | "investigation"
  | "wallet"
  | "transaction"
  | "evidence"
  | "attribution"
  | "vasp"
  | "report";

export interface SearchResult {
  entity_type: SearchEntityType;
  id: string;
  title: string;
  subtitle: string;
  url: string;
  source: string;
  /** Extra per-entity context (risk, confidence, dates, etc). */
  metadata: Record<string, unknown>;
}

export interface GlobalSearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
  source: string;
}

/* ---- Investigator assistant (M9; backend assistant module) ---- */

export type AssistantDataSource = "live" | "demo" | "mixed" | "unavailable";

export type AssistantIntent =
  | "summarize_case"
  | "trace_funds"
  | "find_vasp"
  | "explain_attribution"
  | "suspicious_transactions"
  | "build_timeline"
  | "explain_risk"
  | "generate_report"
  | "prepare_referral"
  | "compare_wallets"
  | "what_changed"
  | "assist";

export interface AssistantQuickAction {
  id: string;
  label: string;
  description: string;
  scope: "case" | "wallet";
  requires_confirmation: boolean;
}

/** Raw backend wire shape: POST /api/v1/assistant/query. */
export interface BackendAssistantRequest {
  query: string;
  intent?: string | null;
  case_id?: string | null;
  wallet_address?: string | null;
  chain: string;
  wallet2?: string | null;
}

export interface AssistantSection {
  heading: string;
  body?: string | null;
  bullets: string[];
  actions: string[];
}

export interface ReferralDraft {
  title: string;
  case_id: string;
  primary_wallet: string;
  chain: string;
  summary: string;
  evidence_ids: string[];
  transaction_hashes: string[];
  vasp_candidates: string[];
  risk_level: string;
  risk_score: number | null;
  submission_state: "draft_for_review" | "requires_sahyog_connection";
  sahyog_status: string;
}

/** Raw backend wire shape: AssistantResponse (assistant module). */
export interface AssistantResponse {
  request_id: string;
  intent: string;
  title: string;
  sections: AssistantSection[];
  evidence_ids: string[];
  transaction_hashes: string[];
  warnings: string[];
  disclaimer: string;
  data_source: AssistantDataSource;
  human_review_required: boolean;
  suggested_actions: AssistantQuickAction[];
  referral_draft: ReferralDraft | null;
}