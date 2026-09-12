/**
 * Access-token store.
 *
 * Persists the signed bearer token (backend auth) in sessionStorage so it is
 * cleared when the tab closes and survives soft reloads. The token is opaque
 * to the frontend: it is only ever sent back in the Authorization header and
 * never logged or serialized into any other storage.
 */

const TOKEN_KEY = "cryptotrace.token";
const TOKEN_EXPIRY_KEY = "cryptotrace.tokenExpiresAt";

export function saveToken(token: string, expiresInSeconds: number): void {
  try {
    window.sessionStorage.setItem(TOKEN_KEY, token);
    const expiresAt = Date.now() + expiresInSeconds * 1000;
    window.sessionStorage.setItem(TOKEN_EXPIRY_KEY, String(expiresAt));
  } catch {
    // Storage unavailable (privacy mode) — token lives in memory only for the
    // caller that just acquired it; the client simply won't re-attach it later.
  }
}

export function getToken(): string | null {
  try {
    return window.sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function clearToken(): void {
  try {
    window.sessionStorage.removeItem(TOKEN_KEY);
    window.sessionStorage.removeItem(TOKEN_EXPIRY_KEY);
  } catch {
    // ignore
  }
}

/** True when a token exists and has not yet passed its recorded expiry. */
export function hasValidToken(): boolean {
  const token = getToken();
  if (!token) return false;
  try {
    const expiryRaw = window.sessionStorage.getItem(TOKEN_EXPIRY_KEY);
    if (!expiryRaw) return true; // no expiry recorded — optimistic
    return Number(expiryRaw) > Date.now();
  } catch {
    return true;
  }
}

export function tokenExpiresAt(): number | null {
  try {
    const raw = window.sessionStorage.getItem(TOKEN_EXPIRY_KEY);
    if (!raw) return null;
    const ms = Number(raw);
    return Number.isFinite(ms) ? ms : null;
  } catch {
    return null;
  }
}