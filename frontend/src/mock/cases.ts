import type { Investigation, InvestigationNote, InvestigationTimelineEvent } from "@/api/types";

/**
 * SYNTHETIC CASE DATA — demo only. Investigation persistence lives on the
 * backend later; these records are clearly marked with isDemo: true.
 */

const now = Date.now();
const h = 3600_000;

export const demoInvestigations: Investigation[] = [
  {
    id: "CT-2026-0142",
    name: "Phishing Sweep — Staking Pool Impersonation",
    description:
      "Funds moved from victim wallets into a clustering of addresses linked to a brand-impersonation phishing operation. Tracing exit liquidity.",
    primaryWallet: "0x7c5bd5c9cde06b8c998a6a66dbdc2e9e8e2f4b13",
    network: "Ethereum",
    risk: "high",
    status: "investigating",
    transactions: 342,
    vaspCandidates: 2,
    evidenceCount: 17,
    assignedAnalyst: "Rohan Iyer",
    createdAt: new Date(now - 9 * 24 * h).toISOString(),
    updatedAt: new Date(now - 2 * h).toISOString(),
    tags: ["phishing", "staking", "USDT"],
    isDemo: true,
  },
  {
    id: "CT-2026-0141",
    name: "Bridge Exit Tracer — Layer2 Consolidation",
    description:
      "High-velocity consolidation across an L1/L2 bridge followed by sequential withdrawals to multiple exchanges.",
    primaryWallet: "0xa1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4",
    network: "Ethereum",
    risk: "critical",
    status: "escalated",
    transactions: 1281,
    vaspCandidates: 3,
    evidenceCount: 41,
    assignedAnalyst: "Rohan Iyer",
    createdAt: new Date(now - 21 * 24 * h).toISOString(),
    updatedAt: new Date(now - 6 * h).toISOString(),
    tags: ["bridge", "cross-chain", "exchange"],
    isDemo: true,
  },
  {
    id: "CT-2026-0137",
    name: "Ransomware Payment Trail",
    description:
      "Ransom payment received into a deposit address and split across token-swap contracts. Candidate attribution to a mixing service underway.",
    primaryWallet: "0xdeadbeef00112233445566778899aabbccddeeff",
    network: "Ethereum",
    risk: "critical",
    status: "open",
    transactions: 618,
    vaspCandidates: 1,
    evidenceCount: 12,
    assignedAnalyst: "Meera Nair",
    createdAt: new Date(now - 6 * 24 * h).toISOString(),
    updatedAt: new Date(now - 1 * h).toISOString(),
    tags: ["ransomware", "mixer", "BTC-swap"],
    isDemo: true,
  },
  {
    id: "CT-2026-0131",
    name: "NFT Rugpull Reconnaissance",
    description:
      "Creator wallet drained liquidity from a contract; mapping OTC and P2P exit points.",
    primaryWallet: "0x98f76a1b2c3d4e5f60718293a4b5c6d7e8f9a0b10",
    network: "Ethereum",
    risk: "medium",
    status: "review",
    transactions: 89,
    vaspCandidates: 0,
    evidenceCount: 6,
    assignedAnalyst: "Meera Nair",
    createdAt: new Date(now - 32 * 24 * h).toISOString(),
    updatedAt: new Date(now - 2 * 24 * h).toISOString(),
    tags: ["nft", "rugpull"],
    isDemo: true,
  },
  {
    id: "CT-2026-0122",
    name: "Inactive Watch — Cold Wallet",
    description:
      "Long-dormant address flagged on a watchlist; monitoring resumption of activity only.",
    primaryWallet: "0x4f3a2b1c09d8e7f6051423a4b5c6d7e8f9a0b1c20",
    network: "Ethereum",
    risk: "low",
    status: "closed",
    transactions: 3,
    vaspCandidates: 0,
    evidenceCount: 1,
    assignedAnalyst: "Kabir Shah",
    createdAt: new Date(now - 60 * 24 * h).toISOString(),
    updatedAt: new Date(now - 14 * 24 * h).toISOString(),
    tags: ["watchlist"],
    isDemo: true,
  },
  {
    id: "CT-2026-0146",
    name: "Draft — DEX Arbitrage Swarm",
    description:
      "Proposed follow-on around a coordinated set of MEV-style wallets. Draft, awaiting assignment.",
    primaryWallet: "0x2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4f50",
    network: "Ethereum",
    risk: "unknown",
    status: "draft",
    transactions: 0,
    vaspCandidates: 0,
    evidenceCount: 0,
    assignedAnalyst: "Unassigned",
    createdAt: new Date(now - 2 * 24 * h).toISOString(),
    updatedAt: new Date(now - 2 * 24 * h).toISOString(),
    tags: ["dex", "mev"],
    isDemo: true,
  },
];

const runtimeCases: Investigation[] = [];

export function addDemoInvestigation(caseData: Investigation): void {
  runtimeCases.push(caseData);
}

export function getDemoInvestigations(): Investigation[] {
  return [...demoInvestigations, ...runtimeCases];
}

export function getDemoInvestigation(id: string): Investigation | undefined {
  return [...demoInvestigations, ...runtimeCases].find((c) => c.id.toLowerCase() === id.toLowerCase());
}

export const demoNotes: InvestigationNote[] = [
  {
    id: "n-1",
    author: "Rohan Iyer",
    createdAt: new Date(now - 7 * 24 * h).toISOString(),
    body: "Initial cluster identified: 14 addresses receive staked-token deposits and forward to a two-hop chain ending at a deposit address.",
  },
  {
    id: "n-2",
    author: "Meera Nair",
    createdAt: new Date(now - 3 * 24 * h).toISOString(),
    body: "Order-flow analysis suggests consolidation windows align with off-peak hours on the destination exchange.",
  },
];

export const demoTimeline: InvestigationTimelineEvent[] = [
  {
    id: "t-1",
    at: new Date(now - 9 * 24 * h).toISOString(),
    actor: "system",
    action: "Case created",
    severity: "info",
    category: "lifecycle",
  },
  {
    id: "t-2",
    at: new Date(now - 9 * 24 * h + 30 * 60_000).toISOString(),
    actor: "system",
    action: "Wallet imported (342 transfers)",
    severity: "info",
    category: "ingestion",
  },
  {
    id: "t-3",
    at: new Date(now - 8 * 24 * h).toISOString(),
    actor: "Rohan Iyer",
    action: "Graph analysis requested (depth 3)",
    severity: "info",
    category: "graph",
  },
  {
    id: "t-4",
    at: new Date(now - 6 * 24 * h).toISOString(),
    actor: "system",
    action: "VASP candidate generated: “StakingPool.io (candidate)”",
    severity: "warning",
    category: "attribution",
  },
  {
    id: "t-5",
    at: new Date(now - 4 * 24 * h).toISOString(),
    actor: "Meera Nair",
    action: "Evidence E-018 attached (transaction)",
    severity: "info",
    category: "evidence",
  },
  {
    id: "t-6",
    at: new Date(now - 2 * 24 * h).toISOString(),
    actor: "system",
    action: "Risk score changed: medium → high",
    severity: "critical",
    category: "risk",
  },
  {
    id: "t-7",
    at: new Date(now - 2 * h).toISOString(),
    actor: "Rohan Iyer",
    action: "Investigation updated",
    severity: "info",
    category: "lifecycle",
  },
];