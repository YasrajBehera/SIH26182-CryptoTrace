import { client, ApiError } from "./client";
import { isDemoMode } from "./config";
import type { HealthStatus, WalletTransfers, WalletSummary } from "./types";
import { getDemoTransfers, getDemoWalletSummary } from "@/mock";

export const wallets = {
  /**
   * Member 1 endpoint: GET /api/v1/wallets/{address}/transfers
   * Falls back to labeled synthetic data when the backend is unreachable.
   */
  async getTransfers(address: string, limit = 500): Promise<WalletTransfers> {
    if (isDemoMode()) {
      return getDemoTransfers(address, limit);
    }
    const res = await client.get<WalletTransfers>(`/api/v1/wallets/${encodeURIComponent(address)}/transfers`, {
      query: { limit },
    });
    return res;
  },

  /**
   * Wallet summary (first seen, volumes, risk) persisted by the wallets module.
   * 404 (no data yet) is an honest "not analyzed" result.
   */
  async getSummary(address: string): Promise<WalletSummary | null> {
    if (isDemoMode()) {
      return getDemoWalletSummary(address);
    }
    try {
      const res = await client.get<BackendWalletSummary>(
        `/api/v1/wallets/${encodeURIComponent(address)}/summary`,
        { query: { chain: "eth" }, timeoutMs: 15000 },
      );
      return {
        address: res.address,
        network: res.network,
        firstSeen: res.first_seen,
        lastActivity: res.last_activity,
        transactionCount: res.transaction_count,
        incomingVolume: res.incoming_volume,
        outgoingVolume: res.outgoing_volume,
        balance: res.balance,
        risk: (res.risk as WalletSummary["risk"]) ?? "unknown",
        riskScore: res.risk_score,
        investigationStatus: (res.investigation_status as WalletSummary["investigationStatus"]) ?? "not_analyzed",
      };
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) return null;
      throw err;
    }
  },
};

interface BackendWalletSummary {
  address: string;
  network: string;
  first_seen: string | null;
  last_activity: string | null;
  transaction_count: number;
  incoming_volume: string;
  outgoing_volume: string;
  balance: string | null;
  risk: string;
  risk_score: number | null;
  investigation_status: string;
  source: string;
}

export const health = {
  async check(): Promise<boolean> {
    try {
      const res = await client.get<HealthStatus>("/api/v1/health", { timeoutMs: 6000 });
      return res.status === "ok";
    } catch {
      return false;
    }
  },
};