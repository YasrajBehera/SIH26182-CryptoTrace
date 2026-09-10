/**
 * Frontend-side public-address formatting and light validation.
 *
 * SECURITY NOTE: The backend (Member 1) is the authoritative validator
 * (full EIP-55 checksum via keccak). This helper only does structural checks
 * for a good UX (lenient to avoid blocking legitimately-still-processing input).
 * It never handles, accepts, or stores any private key / seed phrase material.
 */

export const ADDRESS_PATTERN = /^0x[0-9a-fA-F]{40}$/;

export function isLikelyAddress(value: string): boolean {
  const v = (value || "").trim();
  return ADDRESS_PATTERN.test(v);
}

export function isLikelyHash(value: string): boolean {
  const v = (value || "").trim();
  return /^0x[0-9a-fA-F]{64}$/.test(v);
}

export function normalizeAddressInput(value: string): string {
  return (value || "").trim();
}

export function validateAddressInput(value: string): string | null {
  const v = normalizeAddressInput(value);
  if (!v) return "Enter a wallet address to investigate.";
  if (!/^0x[0-9a-fA-F]{40}$/.test(v)) {
    if (!/^0x/.test(v)) return "Addresses must start with 0x.";
    return "Address must contain 40 hexadecimal characters. Only public addresses are accepted.";
  }
  return null;
}

const FORBIDDEN = /(seed\s*phrase|private\s*key|mnemonic|secret\s*key|passphrase)/i;

/** Reject clearly-secret material before it reaches any input field. */
export function containsSecretMaterial(value: string): boolean {
  return FORBIDDEN.test(value);
}

export function explorerLink(address: string, chain = "eth"): string {
  if (chain !== "eth") return `https://etherscan.io/address/${address}`;
  return `https://etherscan.io/address/${address}`;
}

export function txExplorerLink(hash: string, chain = "eth"): string {
  if (chain !== "eth") return `https://etherscan.io/tx/${hash}`;
  return `https://etherscan.io/tx/${hash}`;
}