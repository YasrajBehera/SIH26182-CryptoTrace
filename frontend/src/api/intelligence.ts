import { isDemoMode } from "./config";
import { client } from "./client";
import type { SanctionsLookup } from "./types";

/**
 * CURATED PUBLIC SANCTIONS / ILLICIT INTELLIGENCE frontend contract.
 *
 * This layer is SEPARATE from VASP attribution and is NEVER presented as a
 * live OFAC integration. Only an exact address match against the curated
 * public directory sets `level: high`. Every other wallet resolves to
 * `level: unknown` (NOT ASSESSED — never "not criminal").
 */

// Mirrors backend/intelligence/curated_sanctions.py so the demo mode shows the
// same curated public record the live backend serves.
/** @internal */
export const DEMO_CURATED_SANCTIONS: SanctionsLookup = {
  address: "0x098b716b8aaf21512996dc57eb0615e2383e2f96",
  chain: "eth",
  matched: true,
  level: "high",
  data_source: "curated_public_intelligence",
  record: {
    record_id: "san-eth-0x098b716b8aaf21512996dc57eb0615e2383e2f96",
    chain: "eth",
    address: "0x098b716b8aaf21512996dc57eb0615e2383e2f96",
    entity: "Lazarus Group",
    classification: "sanctioned",
    source: "OFAC",
    match_type: "exact_address",
    confidence: "HIGH",
    source_type: "public_government",
    reference: "https://sanctionssearch.ofac.treas.gov/",
    notes: "Curated public intelligence; not a live OFAC integration.",
  },
};

export const sanctions = {
  /**
   * Screen a wallet against the curated public sanctions/illicit directory.
   * NEVER a live OFAC integration — the payload always self-labels the data
   * source as CURATED PUBLIC INTELLIGENCE.
   */
  async lookup(address: string, chain = "eth"): Promise<SanctionsLookup | null> {
    if (isDemoMode()) {
      const matches =
        DEMO_CURATED_SANCTIONS.address === address.trim().toLowerCase();
      return matches ? DEMO_CURATED_SANCTIONS : null;
    }
    try {
      return await client.get<SanctionsLookup>(
        `/api/v1/intelligence/sanctions/address/${encodeURIComponent(address)}`,
        { query: { chain }, timeoutMs: 8000 },
      );
    } catch {
      return null;
    }
  },
};