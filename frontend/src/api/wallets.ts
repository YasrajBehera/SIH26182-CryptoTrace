import { client } from "./client";
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
   * Wallet summary (first seen, volumes, risk).
   * WAITING FOR MEMBER 1/backend support: derived server-side later.
   * Today it is synthetic when the backend is unreachable.
   */
  async getSummary(address: string): Promise<WalletSummary | null> {
    if (isDemoMode()) {
      return getDemoWalletSummary(address);
    }
    return null;
  },
};

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