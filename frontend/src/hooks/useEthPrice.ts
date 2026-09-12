import { useEffect, useState } from "react";
import { cachedEthPriceUsd, getEthPriceUsd } from "@/api/marketdata";

/**
 * Best available ETH/USD rate for fiat estimates.
 *
 * Initialises synchronously from cache/demo reference so first paint is
 * deterministic (no async flicker); a background live refresh then updates the
 * value when the cache is stale or absent.
 */
export function useEthPrice(): number | null {
  const [price, setPrice] = useState<number | null>(() => cachedEthPriceUsd());

  useEffect(() => {
    let cancelled = false;
    getEthPriceUsd()
      .then((p) => {
        if (!cancelled) setPrice((prev) => (p !== prev ? p : prev));
      })
      .catch(() => {
        // live lookups already return null on failure; nothing to do here
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return price;
}