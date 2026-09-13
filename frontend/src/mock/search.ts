import type { GlobalSearchResponse, SearchEntityType, SearchResult } from "@/api/types";

/**
 * SYNTHETIC SEARCH RESULTS — clearly labeled. Served only when the backend is
 * unreachable. These hits mirror the demo datasets (cases, wallets, transfers,
 * attribution, VASP directory) and must never be presented as real
 * intelligence.
 */

const demoCasesIntl = [
  { id: "CT-2026-0142", name: "Phishing Sweep - Staking Pool Impersonation", wallet: "0x7c5bd5c9cde06b8c998a6a66dbdc2e9e8e2f4b13", risk: "high" },
  { id: "CT-2026-0141", name: "Bridge Exit Tracer - Layer2 Consolidation", wallet: "0xa1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4", risk: "critical" },
  { id: "CT-2026-0138", name: "Mixing Service Round Trip", wallet: "0xdeadbeef00112233445566778899aabbccddeeff", risk: "high" },
];

const demoWalletAddrs = [
  "0x7c5bd5c9cde06b8c998a6a66dbdc2e9e8e2f4b13",
  "0xa1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4",
  "0xdeadbeef00112233445566778899aabbccddeeff",
  "0x98f76a1b2c3d4e5f60718293a4b5c6d7e8f9a0b10",
  "0x4f3a2b1c09d8e7f6051423a4b5c6d7e8f9a0b1c20",
];

const demoVasps = [
  "Binance",
  "Coinbase Prime",
  "Kraken",
  "OKX",
  "KuCoin",
];

function includesAny(haystack: string, needle: string): boolean {
  return haystack.toLowerCase().includes(needle.toLowerCase());
}

function buildResults(q: string): SearchResult[] {
  const needle = q.trim();
  if (!needle) return [];
  // Substring match against the id/title/wallet/again-labels; bounded,
  // relevance-ordered results for a small demo dataset.
  const out: SearchResult[] = [];

  for (const c of demoCasesIntl) {
    if (includesAny(`${c.id} ${c.name} ${c.wallet}`, needle)) {
      out.push({
        entity_type: "investigation",
        id: c.id,
        title: c.name,
        subtitle: `Case ${c.id} - risk ${c.risk}`,
        url: `/cases/${c.id}`,
        source: "demo",
        metadata: { risk: c.risk, wallet: c.wallet },
      });
    }
  }

  for (const addr of demoWalletAddrs) {
    if (includesAny(addr, `0x${needle.replace(/^0x/i, "")}`) || includesAny(addr, needle)) {
      out.push({
        entity_type: "wallet",
        id: addr,
        title: addr,
        subtitle: "Ethereum wallet - synthetic demo record",
        url: `/wallets/${addr}`,
        source: "demo",
        metadata: { chain: "eth", risk: "pending" },
      });
    }
  }

  // One labeled-synthetic transaction match so the transfers view links through.
  const demoHash =
    "0x5f7aab3c91d2e8b45f6c0a2d19e7b8c6d5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c";
  if (includesAny(demoHash, needle)) {
    out.push({
      entity_type: "transaction",
      id: demoHash,
      title: demoHash.slice(0, 24) + "...",
      subtitle: "Synthetic demo transfer hash",
      url: `/transactions?wallet=${demoWalletAddrs[0]}&hash=${demoHash}`,
      source: "demo",
      metadata: { chain: "eth", value: "12,500.00" },
    });
  }

  for (const v of demoVasps) {
    if (includesAny(v, needle)) {
      out.push({
        entity_type: "vasp",
        id: v.toLowerCase().replace(/\s+/g, "-"),
        title: v,
        subtitle: "Curated VASP directory entry (demo)",
        url: "/vasp",
        source: "demo",
        metadata: { type: "exchange", jurisdiction: "global" },
      });
    }
  }

  return out;
}

export function getDemoSearchResults(
  q: string,
  entityType?: SearchEntityType,
  limit = 20,
): GlobalSearchResponse {
  const results = buildResults(q)
    .filter((r) => !entityType || r.entity_type === entityType)
    .slice(0, limit);
  return {
    query: q,
    results,
    total: results.length,
    source: "demo",
  };
}