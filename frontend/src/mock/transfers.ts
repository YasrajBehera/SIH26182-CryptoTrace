import type { BlockchainTransfer, WalletTransfers } from "@/api/types";

/**
 * SYNTHETIC DATA — clearly labeled. Used when the Member 1 backend is
 * unreachable. These transfers are fabricated for UI development only and
 * must never be presented as real blockchain intelligence.
 */

const ASSETS = ["ETH", "USDT", "USDC", "DAI", "LINK", "UNI"];

function fakeHex64(i: number): string {
  return `0x${(i * 2654435761 + 0xfeed).toString(16).padStart(64, "0")}`;
}

function fakeAddress(seed: number): string {
  const part = (seed * 0x9e3779b1) % 0xffffffff;
  return `0x${part.toString(16).padStart(40, "0")}`;
}

function seeded(i: number): number {
  const x = Math.sin(i * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

/** Deterministic synthetic transfer set for a given wallet address.

The backing set is fixed at 64 labeled-synthetic rows so pages can be
requested by `offset`/`limit` exactly like the live backend paginates its held
set. `direction` filters the backing set (applied before paging), the same way
the live endpoint restricts its fetch. Always synthetic, never real on-chain.
*/
export function getDemoTransfers(address: string, limit = 60, offset = 0, direction?: string): WalletTransfers {
  const seedBase = [...address].reduce((a, c) => a + c.charCodeAt(0), 0);
  const total = 64;

  const all: BlockchainTransfer[] = Array.from({ length: total }, (_, i) => {
    const seed = seedBase + i;
    const dir: BlockchainTransfer["direction"] = seeded(seed) > 0.5 ? "in" : "out";
    const asset = ASSETS[Math.floor(seeded(seed + 1) * ASSETS.length)];
    const valueRaw = Math.floor(seeded(seed + 2) * 1e6) * 100 + 100;
    const ts = Date.now() - i * 1000 * 60 * 60 * 47;
    const syntheticFrom = dir === "in" ? fakeAddress(Math.floor(seeded(seed + 3) * 1e6)) : address;
    const syntheticTo = dir === "out" ? fakeAddress(Math.floor(seeded(seed + 4) * 1e6)) : address;
    const isInternal = seeded(seed + 5) > 0.9;
    const category = isInternal ? "internal" : asset === "ETH" ? "external" : "erc20";

    return {
      transaction_hash: fakeHex64(seed + 1),
      block_number: 19_300_000 + Math.floor(seeded(seed + 6) * 900_000),
      block_timestamp: new Date(ts).toISOString(),
      from_address: syntheticFrom.toLowerCase(),
      to_address: syntheticTo.toLowerCase(),
      value: String(valueRaw),
      asset,
      category,
      direction: dir,
      raw_contract_address: category === "erc20" ? `0x${((seed % 0xffffffffff) + 0x1a2b3c4d5e).toString(16).padStart(40, "0")}` : null,
      raw_contract_value: category === "erc20" ? `0x${valueRaw.toString(16)}` : null,
      chain: "eth",
    };
  });

  all.sort((a, b) => (a.block_timestamp! > b.block_timestamp! ? 1 : -1));

  const filtered = direction === "in" || direction === "out" ? all.filter((t) => t.direction === direction) : all;
  const safeOffset = Math.max(0, Math.min(offset, filtered.length));
  const page = filtered.slice(safeOffset, safeOffset + limit);

  return {
    wallet_address: address.toLowerCase(),
    chain: "eth",
    transfers: page,
    pagination: {
      max_transfers: limit,
      fetched: page.length,
      truncated: false,
      offset: safeOffset,
      limit,
      total: filtered.length,
      has_next: safeOffset + page.length < filtered.length,
      has_previous: safeOffset > 0,
    },
  };
}

export const demoTransfers = getDemoTransfers("0xdemo000000000000000000000000000000000000");
export { demoTransfers as demoTransfers_public };

export const demoWallets = [
  "0x7c5bd5c9cde06b8c998a6a66dbdc2e9e8e2f4b13",
  "0xa1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4",
  "0xdeadbeef00112233445566778899aabbccddeeff",
  "0x98f76a1b2c3d4e5f60718293a4b5c6d7e8f9a0b10",
  "0x4f3a2b1c09d8e7f6051423a4b5c6d7e8f9a0b1c20",
];