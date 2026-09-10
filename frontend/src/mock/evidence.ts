import type { AuditEvent, EvidenceItem, ProvenanceLink } from "@/api/types";

/**
 * SYNTHETIC EVIDENCE + AUDIT DATA — demo only. These records are clearly
 * marked; real evidence/provenance will come from the backend (Member 3).
 */

export const demoEvidence: EvidenceItem[] = [
  {
    id: "E-018",
    type: "blockchain_transaction",
    title: "Tx 0x9f2a…33bb — consolidated deposit",
    source: "Ethereum mainnet (Alchemy ingestion)",
    createdBy: "Meera Nair",
    createdAt: "2026-09-06T11:05:00Z",
    relatedWallet: "0x7c5bd5c9cde06b8c998a6a66dbdc2e9e8e2f4b13",
    relatedTransaction: "0x9f2a33bb44cc55dd66ee77ff8800112233445566778899aabbccddeeff3344",
    relatedCandidate: "cand-1",
    reliability: "high",
    checksum: "sha256:11f4…9c2e",
    notes: "Normalized transfer with metadata; chain header timestamp cross-checked.",
    isDemo: true,
  },
  {
    id: "E-019",
    type: "address_intelligence",
    title: "Curated VASP address list entry",
    source: "Curated list v3 (pending independent verification)",
    createdBy: "Rohan Iyer",
    createdAt: "2026-09-07T06:20:00Z",
    relatedWallet: "0x70819a0b1c2d3e4f5061728394a5b6c7d8e9f0a1",
    relatedCandidate: "cand-1",
    reliability: "medium",
    checksum: "sha256:8a1d…77b0",
    notes: "Marked unverified — do not treat as confirmed ownership.",
    isDemo: true,
  },
  {
    id: "E-020",
    type: "system_observation",
    title: "Cluster graph snapshot at depth 3",
    source: "Graph analysis stub",
    createdBy: "system",
    createdAt: "2026-09-07T19:41:00Z",
    relatedWallet: "0x7c5bd5c9cde06b8c998a6a66dbdc2e9e8e2f4b13",
    relatedCandidate: "cand-1",
    reliability: "high",
    checksum: "sha256:22ab…0e91",
    isDemo: true,
  },
  {
    id: "E-021",
    type: "analyst_note",
    title: "Investigator observation — consolidation windows",
    source: "Analyst workstation",
    createdBy: "Rohan Iyer",
    createdAt: "2026-09-08T02:31:00Z",
    relatedWallet: "0x7c5bd5c9cde06b8c998a6a66dbdc2e9e8e2f4b13",
    relatedCandidate: "cand-2",
    reliability: "medium",
    notes: "Consolidation aligns with off-peak exchange settlement windows.",
    isDemo: true,
  },
  {
    id: "E-022",
    type: "document",
    title: "Open-source phishing report",
    source: "External source: incident report (public)",
    createdBy: "Meera Nair",
    createdAt: "2026-09-05T14:02:00Z",
    relatedCandidate: "cand-1",
    reliability: "low",
    checksum: "sha256:37cf…a812",
    notes: "Public report; corroborating indicators only.",
    isDemo: true,
  },
];

export function getDemoEvidence(): EvidenceItem[] {
  return demoEvidence;
}

export function getDemoProvenance(): ProvenanceLink[] {
  return [
    { id: "p1", label: "Candidate: StakingPool.io", sublabel: "cand-1 · medium confidence", kind: "candidate" },
    { id: "p2", label: "Evidence E-018", sublabel: "blockchain_transaction", kind: "evidence" },
    { id: "p3", label: "Transaction 0x9f2a…3344", sublabel: "normalized transfer", kind: "transaction" },
    { id: "p4", label: "Wallet 0x7c5b…4b13", sublabel: "queried wallet", kind: "wallet" },
    { id: "p5", label: "Ethereum mainnet (Alchemy)", sublabel: "provider ingestion", kind: "source" },
  ];
}

export const demoAuditEvents: AuditEvent[] = [
  {
    id: "au-1",
    timestamp: "2026-09-09T12:04:11Z",
    user: "rohan.inv",
    action: "VIEW",
    resource: "wallet",
    resourceId: "0x7c5bd5c9cde06b8c998a6a66dbdc2e9e8e2f4b13",
    ip: "10.20.4.12",
    result: "success",
    isDemo: true,
  },
  {
    id: "au-2",
    timestamp: "2026-09-09T12:03:45Z",
    user: "meera.analyst",
    action: "CREATE",
    resource: "evidence",
    resourceId: "E-022",
    ip: "10.20.4.18",
    result: "success",
    isDemo: true,
  },
  {
    id: "au-3",
    timestamp: "2026-09-09T11:58:02Z",
    user: "kabir.review",
    action: "UPDATE",
    resource: "investigation",
    resourceId: "CT-2026-0131",
    ip: "10.20.7.3",
    result: "success",
    isDemo: true,
  },
  {
    id: "au-4",
    timestamp: "2026-09-09T11:40:29Z",
    user: "nisha.read",
    action: "EXPORT",
    resource: "report",
    resourceId: "CT-RPT-0137",
    ip: "10.20.9.9",
    result: "denied",
    isDemo: true,
  },
  {
    id: "au-5",
    timestamp: "2026-09-09T11:21:18Z",
    user: "rohan.inv",
    action: "ATTRIBUTION_REQUEST",
    resource: "candidate",
    resourceId: "cand-1",
    ip: "10.20.4.12",
    result: "success",
    isDemo: true,
  },
  {
    id: "au-6",
    timestamp: "2026-09-09T10:02:00Z",
    user: "system",
    action: "LOGIN",
    resource: "session",
    resourceId: "u-inv",
    ip: "10.20.4.12",
    result: "success",
    isDemo: true,
  },
  {
    id: "au-7",
    timestamp: "2026-09-09T09:44:36Z",
    user: "meera.analyst",
    action: "DELETE",
    resource: "evidence",
    resourceId: "E-014",
    ip: "10.20.4.18",
    result: "denied",
    isDemo: true,
  },
];

export function getDemoAuditEvents(): AuditEvent[] {
  return demoAuditEvents;
}