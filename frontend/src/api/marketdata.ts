import { logger } from "@/lib/logger";
import { isDemoMode } from "./config";

/**
 * Fiat-USD market data.
 *
 * Live mode fetches the ETH/USD reference rate from CoinGecko's free
 * public endpoint (no key) and caches it for one hour so the UI degrades
 * gracefully offline. Demo/offline mode uses a fixed labeled reference rate
 * so fiat estimates still render for synthetic data.
 *
 * Only ETH-denominated amounts receive a USD estimate; stablecoins and
 * ERC-20 tokens are left untouched to avoid inventing prices.
 */

const DEMO_ETH_USD = 3500;
const CACHE_KEY = "cryptotrace.ethusd.v1";
const CACHE_TTL_MS = 60 * 60 * 1000;

interface PriceCache {
  at: number;
  usd: number;
}

let memoryCache: number | null = null;

function readCache(): number | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PriceCache;
    if (!parsed || typeof parsed.usd !== "number" || typeof parsed.at !== "number") return null;
    if (Date.now() - parsed.at > CACHE_TTL_MS) return null;
    return parsed.usd;
  } catch {
    return null;
  }
}

async function fetchLivePrice(): Promise<number> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 6000);
  try {
    const res = await fetch(
      "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd",
      { signal: controller.signal },
    );
    if (!res.ok) throw new Error(`price fetch failed (${res.status})`);
    const data = (await res.json()) as { ethereum?: { usd?: number } };
    const usd = data.ethereum?.usd;
    if (typeof usd !== "number" || !Number.isFinite(usd)) throw new Error("unexpected price payload");
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({ at: Date.now(), usd } satisfies PriceCache));
    } catch {
      // storage may be unavailable; memory cache still covers this session
    }
    memoryCache = usd;
    return usd;
  } finally {
    window.clearTimeout(timer);
  }
}

/**
 * Synchronous best-known price for initial render: returns the session/local
 * cache, or the demo reference constant in demo mode. Live mode returns null
 * until the async refresh completes.
 */
export function cachedEthPriceUsd(): number | null {
  const cached = readCache();
  if (cached !== null) return cached;
  return isDemoMode() ? DEMO_ETH_USD : null;
}

/** Best available ETH/USD reference, or null when live lookups fail. */
export async function getEthPriceUsd(): Promise<number | null> {
  if (!isDemoMode()) {
    if (memoryCache !== null) return memoryCache;
    const cached = readCache();
    if (cached !== null) return cached;
    try {
      return await fetchLivePrice();
    } catch (err) {
      logger.warn("ETH price unavailable", { error: String(err) });
      return null;
    }
  }
  return readCache() ?? DEMO_ETH_USD;
}

/**
 * USD estimate for a crypto amount. Returns null when no trustworthy price is
 * available or when the asset is not ETH-denominated (we never invent prices).
 */
export function estimateUsd(cryptoAmount: string | number, priceUsd: number | null, asset?: string | null): number | null {
  if (priceUsd === null || priceUsd === undefined) return null;
  const amount = Number(cryptoAmount);
  if (!Number.isFinite(amount)) return null;
  const a = (asset ?? "").toLowerCase();
  if (a && a !== "eth" && a !== "weth") return null;
  return amount * priceUsd;
}