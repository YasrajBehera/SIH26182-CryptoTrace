const ELLIPSIS = "…";

/** Truncate a blockchain address for display: 0x1234...abcd */
export function shortenAddress(address?: string | null, head = 6, tail = 4): string {
  if (!address) return "";
  const a = address.trim();
  if (a.length <= head + tail + 1) return a;
  return `${a.slice(0, head)}${ELLIPSIS}${a.slice(-tail)}`;
}

/** Truncate a long transaction hash: 0x1234...abcd */
export function shortenHash(hash?: string | null, head = 10, tail = 8): string {
  return shortenAddress(hash, head, tail);
}

const CHAIN_NAME: Record<string, string> = {
  eth: "Ethereum",
  "eth-mainnet": "Ethereum Mainnet",
  goerli: "Ethereum Goerli",
  sepolia: "Ethereum Sepolia",
};

export function chainLabel(chain?: string | null): string {
  if (!chain) return "Unknown network";
  return CHAIN_NAME[chain] ?? chain;
}

/**
 * Format a raw on-chain value string into a human figure.
 * Values are strings to preserve precision; we only format, never round production data.
 */
export function formatAmount(value?: string | number | null, asset?: string | null): string {
  if (value === undefined || value === null || value === "") return "—";
  const num = Number(value);
  if (!Number.isFinite(num)) return value.toString();

  const abs = Math.abs(num);
  let out: string;
  if (abs >= 1_000_000_000) out = `${(num / 1_000_000_000).toFixed(2)}B`;
  else if (abs >= 1_000_000) out = `${(num / 1_000_000).toFixed(2)}M`;
  else if (abs >= 1_000) out = `${(num / 1_000).toFixed(2)}K`;
  else if (abs >= 1) out = num.toLocaleString("en-US", { maximumFractionDigits: 4 });
  else out = num.toPrecision(3);

  return asset ? `${out} ${asset}` : out;
}

export function formatNumber(value?: number | null): string {
  if (value === undefined || value === null) return "—";
  return value.toLocaleString("en-US");
}

export function formatUsd(value?: number | null): string {
  if (value === undefined || value === null) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatDate(value?: string | Date | null): string {
  if (!value) return "—";
  const d = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function fromNow(value?: string | Date | null): string {
  if (!value) return "—";
  const d = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(d.getTime())) return String(value);
  const diffMs = Date.now() - d.getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.round(days / 30);
  if (months < 12) return `${months}mo ago`;
  return `${Math.round(months / 12)}y ago`;
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function pluralize(count: number, word: string): string {
  return count === 1 ? word : `${word}s`;
}

/** Deterministic pseudo-id for local/demo records. */
export function uid(prefix = "x"): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}