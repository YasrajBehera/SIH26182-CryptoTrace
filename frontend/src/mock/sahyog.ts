/**
 * SYNTHETIC SAHYOG REFERRAL DATA — demo only.
 *
 * Simulates I4C cybercrime-referral intake:
 * complaint → suspect-wallet → triage → hand off to CryptoTrace investigation.
 */

export interface SahyogReferral {
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

const now = Date.now();
const d = 24 * 60 * 60 * 1000;

export const sahyogReferrals: SahyogReferral[] = [
  {
    id: "REF-2026-041",
    firNo: "FIR-MH-2026-18742",
    reportedAt: new Date(now - 3 * d).toISOString(),
    victimName: "Arjun Mehta",
    amountUSDT: 12450,
    suspectWallet: "0x7a3bc9e2d4f108c6b9e7124a5f0c3d8e9a1b2c3d",
    chain: "eth",
    status: "new",
  },
  {
    id: "REF-2026-042",
    firNo: "FIR-DL-2026-09211",
    reportedAt: new Date(now - 2 * d).toISOString(),
    victimName: "Priya Sharma",
    amountUSDT: 5200,
    suspectWallet: "0xde12ad000000000000000000000000000000a1b2",
    chain: "eth",
    status: "new",
  },
  {
    id: "REF-2026-043",
    firNo: "FIR-KA-2026-03876",
    reportedAt: new Date(now - 7 * d).toISOString(),
    victimName: "Vikram Joshi",
    amountUSDT: 87000,
    suspectWallet: "0xbeef00000000000000000000000000000000face",
    chain: "eth",
    status: "triaged",
    triage: {
      risk: "high",
      walletAgeMonths: 2,
      exchangeExposed: true,
      priorFlags: 3,
      recommendation: "investigate",
      triagedBy: "Rohan Iyer",
      triagedAt: new Date(now - 5 * d).toISOString(),
    },
  },
  {
    id: "REF-2026-044",
    firNo: "FIR-TN-2026-02998",
    reportedAt: new Date(now - 10 * d).toISOString(),
    victimName: "Lakshmi Rajan",
    amountUSDT: 1900,
    suspectWallet: "0xc01d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d",
    chain: "eth",
    status: "handed_off",
    triage: {
      risk: "medium",
      walletAgeMonths: 14,
      exchangeExposed: false,
      priorFlags: 0,
      recommendation: "monitor",
      triagedBy: "Aarav Kapoor",
      triagedAt: new Date(now - 8 * d).toISOString(),
    },
    handoffCaseId: "CT-2026-0149",
  },
  {
    id: "REF-2026-045",
    firNo: "FIR-RJ-2026-06102",
    reportedAt: new Date(now - 1 * d).toISOString(),
    victimName: "Deepak Gupta",
    amountUSDT: 34000,
    suspectWallet: "0xfee000000000000000000000000000000000dead",
    chain: "eth",
    status: "triaged",
    triage: {
      risk: "high",
      walletAgeMonths: 1,
      exchangeExposed: true,
      priorFlags: 5,
      recommendation: "investigate",
      triagedBy: "Rohan Iyer",
      triagedAt: new Date(now - 1 * d + 2 * 3600_000).toISOString(),
    },
  },
  {
    id: "REF-2026-046",
    firNo: "FIR-GJ-2026-11088",
    reportedAt: new Date(now - 14 * d).toISOString(),
    victimName: "Neha Kulkarni",
    amountUSDT: 450,
    suspectWallet: "0xaa11bb22cc33dd44ee55ff667788990011223344",
    chain: "eth",
    status: "handed_off",
    triage: {
      risk: "low",
      walletAgeMonths: 36,
      exchangeExposed: false,
      priorFlags: 0,
      recommendation: "watchlist",
      triagedBy: "Meera Nair",
      triagedAt: new Date(now - 12 * d).toISOString(),
    },
    handoffCaseId: "CT-2026-0138",
  },
];

export function createDemoReferrals(): SahyogReferral[] {
  return sahyogReferrals.map((r) => ({ ...r, triage: r.triage ? { ...r.triage } : undefined }));
}
