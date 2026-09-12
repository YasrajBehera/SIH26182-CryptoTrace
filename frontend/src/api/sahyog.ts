import { client } from "./client";
import { isDemoMode } from "./config";
import type { SahyogBackendOut, SahyogCreateInput, SahyogReferralView } from "./types";

/**
 * SAHYOG referral intake adapter (DEMO flow).
 *
 * The backend SAHYOG module simulates I4C referral intake with honest status
 * transitions (new -> triaged -> handed_off). Live mode talks to it; demo mode
 * keeps using the synthetic local dataset. All referral data is synthetic and
 * never claimed to be a real I4C/NCRP feed.
 */

const RISK_ORDER = ["high", "medium", "low"] as const;
const RECOMMENDATIONS = ["investigate", "monitor", "watchlist"] as const;

export function mapBackendSahyogToView(r: SahyogBackendOut): SahyogReferralView {
  const rawTriage = (r.triage ?? {}) as Record<string, unknown>;
  const isRisk = (v: unknown): v is "high" | "medium" | "low" =>
    typeof v === "string" && (RISK_ORDER as readonly string[]).includes(v);
  const isRecommendation = (v: unknown): v is "investigate" | "monitor" | "watchlist" =>
    typeof v === "string" && (RECOMMENDATIONS as readonly string[]).includes(v);
  const risk = isRisk(rawTriage.risk) ? rawTriage.risk : undefined;
  const recommendation = isRecommendation(rawTriage.recommendation)
    ? rawTriage.recommendation
    : undefined;

  const triage =
    risk && recommendation
      ? {
          risk,
          walletAgeMonths: (rawTriage.wallet_age_months as number) ?? 0,
          exchangeExposed: rawTriage.exchange_exposed as boolean,
          priorFlags: (rawTriage.prior_flags as number) ?? 0,
          recommendation,
          triagedBy: (rawTriage.triaged_by as string) ?? "",
          triagedAt: (rawTriage.triaged_at as string) ?? "",
        }
      : undefined;

  return {
    id: r.id,
    firNo: r.fir_no,
    reportedAt: r.reported_at ?? new Date(0).toISOString(),
    victimName: r.victim_name,
    amountUSDT: r.amount_usdt,
    suspectWallet: r.suspect_wallet,
    chain: r.chain === "btc" ? "btc" : "eth",
    status: (r.status as SahyogReferralView["status"]) ?? "new",
    triage,
    handoffCaseId: r.handoff_case_id ?? undefined,
  };
}

export const sahyog = {
  async list(): Promise<SahyogReferralView[]> {
    if (isDemoMode()) return [];
    const res = await client.get<SahyogBackendOut[]>("/api/v1/sahyog/referrals");
    return res.map(mapBackendSahyogToView);
  },

  async get(id: string): Promise<SahyogReferralView | null> {
    if (isDemoMode()) return null;
    try {
      const res = await client.get<SahyogBackendOut>(`/api/v1/sahyog/referrals/${encodeURIComponent(id)}`);
      return mapBackendSahyogToView(res);
    } catch {
      return null;
    }
  },

  async ingest(input: SahyogCreateInput): Promise<SahyogReferralView> {
    if (isDemoMode()) throw new Error("Referrals are managed locally in demo mode.");
    const res = await client.post<SahyogBackendOut>("/api/v1/sahyog/referrals", {
      fir_no: input.firNo,
      victim_name: input.victimName,
      amount_usdt: input.amountUSDT,
      suspect_wallet: input.suspectWallet,
      chain: input.chain,
    });
    return mapBackendSahyogToView(res);
  },

  async triage(id: string): Promise<SahyogReferralView> {
    if (isDemoMode()) throw new Error("Referrals are managed locally in demo mode.");
    const res = await client.post<SahyogBackendOut>(
      `/api/v1/sahyog/referrals/${encodeURIComponent(id)}/triage`,
      {},
    );
    return mapBackendSahyogToView(res);
  },

  async handoff(
    id: string,
    opts: { caseName?: string; description?: string; priority?: string } = {},
  ): Promise<SahyogReferralView> {
    if (isDemoMode()) throw new Error("Referrals are managed locally in demo mode.");
    const res = await client.post<SahyogBackendOut>(
      `/api/v1/sahyog/referrals/${encodeURIComponent(id)}/handoff`,
      {
        case_name: opts.caseName,
        description: opts.description,
        priority: opts.priority ?? "normal",
      },
    );
    return mapBackendSahyogToView(res);
  },

  async demoNotice(): Promise<string> {
    if (isDemoMode()) {
      return "SAHYOG flow is a DEMO simulation. Referrals are created locally and never leave the browser.";
    }
    try {
      const res = await client.get<{ notice: string }>("/api/v1/sahyog/demo-notice");
      return res.notice;
    } catch {
      return "SAHYOG flow is a DEMO simulation. No live SAHYOG/LE intake connection is used.";
    }
  },
};