import { ApiError, client } from "./client";
import { isDemoMode } from "./config";
import type { BackendRiskAssessment, MLRiskAssessment } from "./types";

/**
 * Analytical risk + ML suspicious-wallet frontend contract.
 *
 * - ``forWallet`` returns the LATEST PERSISTED analytical risk assessment
 *   (404 -> null: no investigation has stored one yet).
 * - ``ml`` computes the ML suspicious-wallet signal LIVE from real on-chain
 *   transfers. It never fabricates: with no trained artifact it reports
 *   ``not_trained``; when required features are missing it reports
 *   ``unavailable`` (UNKNOWN / NOT ASSESSED) with the missing features listed.
 *
 * The ML probability is SEPARATE from the analytical VASP/attribution score
 * and from the criminal/sanctions block, and is never a determination of
 * criminality. Provider/unavailable responses degrade to ``null`` so pages can
 * render an honest UNKNOWN / NOT ASSESSED state.
 */
export const risk = {
  async forWallet(
    address: string,
    chain = "eth",
    signal?: AbortSignal,
  ): Promise<BackendRiskAssessment | null> {
    if (isDemoMode()) return null;
    try {
      return await client.get<BackendRiskAssessment>(
        `/api/v1/risk/wallet/${encodeURIComponent(address)}`,
        { query: { chain }, signal },
      );
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) return null;
      throw err;
    }
  },

  async ml(
    address: string,
    chain = "eth",
    signal?: AbortSignal,
  ): Promise<MLRiskAssessment | null> {
    if (isDemoMode()) return null;
    try {
      return await client.get<MLRiskAssessment>(
        `/api/v1/risk/wallet/${encodeURIComponent(address)}/ml`,
        { query: { chain }, signal },
      );
    } catch (err) {
      if (err instanceof ApiError && [404, 502, 503, 504].includes(err.status)) return null;
      throw err;
    }
  },
};