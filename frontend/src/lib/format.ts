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

/**
 * Parse a timestamp from any supported on-chain/API shape into a Date.
 *
 * Accepts:
 *  - Unix seconds (10 digit, e.g. 1743477239)
 *  - Unix milliseconds (13 digit)
 *  - ISO 8601 strings ("2025-04-01T05:30:00Z")
 *  - Date instances
 *
 * A plain numeric string is treated as unix seconds unless its magnitude
 * implies milliseconds. Invalid/null values return null (never throw).
 * There is deliberately no double conversion: callers pass the value out of
 * Alchemy/db/neo4j exactly once.
 */
export function parseTimestamp(value?: string | number | Date | null): Date | null {
  if (value === null || value === undefined || value === "") return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return null;
    return toDateFromEpoch(value);
  }
  const trimmed = value.trim();
  if (/^-?\d{1,16}(\.\d+)?$/.test(trimmed)) {
    return toDateFromEpoch(Number(trimmed));
  }
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

function toDateFromEpoch(n: number): Date | null {
  // > 1e12 implies epoch milliseconds (e.g. 1.7e12); otherwise unix seconds.
  const ms = n > 1e12 ? n : n * 1000;
  const d = new Date(ms);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** The display timezone (IANA name, e.g. "Asia/Kolkata"). Always shown. */
export function localTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

/**
 * Format a timestamp in the viewer's timezone with the timezone always shown.
 * Stable, locale-independent output: "01 Apr 2025, 05:30 Asia/Kolkata".
 */
export function formatTimestamp(value?: string | number | Date | null): string {
  const d = parseTimestamp(value);
  if (!d) return "—";
  const date = d.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
  const time = d.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return `${date}, ${time} ${localTimeZone()}`;
}

/**
 * Honest source label for a displayed timestamp.
 *  - live: "Blockchain timestamp · Source: Ethereum Mainnet"
 *  - demo: "Synthetic timestamp · Source: Demo data"
 * A synthetic value is never labelled as a blockchain timestamp.
 */
export function timestampSourceLabel(opts: {
  demo?: boolean;
  chain?: string | null;
}): string {
  if (opts.demo) return "Synthetic timestamp · Source: Demo data";
  return `Blockchain timestamp · Source: ${chainLabel(opts.chain)}`;
}

export function formatDate(value?: string | number | Date | null): string {
  const d = parseTimestamp(value);
  if (!d) return "—";
  return d.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function fromNow(value?: string | number | Date | null): string {
  const d = parseTimestamp(value);
  if (!d) return "—";
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