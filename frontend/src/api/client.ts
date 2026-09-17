import { logger } from "@/lib/logger";
import { clearToken, getToken } from "@/auth/tokenStore";

/**
 * Typed fetch client.
 *
 * - All requests go through the Vite dev proxy (`/api` -> backend) so the
 *   backend's Alchemy key never reaches the browser.
 * - When a bearer token exists it is attached automatically as
 *   `Authorization: Bearer <token>` so protected endpoints are exercised.
 * - On a 401 the (now invalid) token is discarded and a
 *   `cryptotrace:unauthorized` event is fired so the session layer can prompt
 *   a clean re-login instead of leaving the user on a dead error screen.
 * - Errors are normalized into user-safe messages: no stack traces, no
 *   database details, no internal infrastructure data, no keys.
 */

const SESSION_EXPIRED_EVENT = "cryptotrace:unauthorized";

export const API_BASE = import.meta.env.VITE_API_BASE_URL || "";// same origin; vite proxy handles /api

export interface ApiErrorBody {
  detail?: string;
  message?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly safe: boolean;

  constructor(message: string, opts: { status?: number; code?: string; safe?: boolean } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = opts.status ?? 0;
    this.code = opts.code ?? "request_failed";
    this.safe = opts.safe ?? true;
  }
}

const SAFE_MESSAGES: Record<number, string> = {
  400: "The request was invalid. Check the wallet address and try again.",
  401: "Authorization is required to access this resource.",
  403: "You do not have permission to perform this action.",
  404: "The requested resource was not found.",
  408: "The request timed out.",
  409: "The request conflicts with the current state.",
  422: "The request could not be processed. Review the submitted values.",
  429: "Too many requests. Please wait and try again.",
  500: "An internal service error occurred. Try again shortly.",
  502: "Blockchain data is currently unavailable. The data provider may be down or misconfigured.",
  503: "The service is temporarily unavailable. Please try again later.",
  504: "The upstream service timed out. Please try again later.",
};

function userSafeMessage(status: number, detail?: string): string {
  const base = SAFE_MESSAGES[status] ?? "An unexpected error occurred.";
  if (detail && status === 400) return detail;
  return base;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | null | undefined>;
  timeoutMs?: number;
  headers?: Record<string, string>;
  /** When true, resolve with the raw response body as a Blob plus its headers. */
  asBlob?: boolean;
  /** External cancellation signal (e.g. from useApi on unmount). */
  signal?: AbortSignal;
}

export interface BlobResult {
  blob: Blob;
  headers: Headers;
}

/**
 * In-flight GET de-duplication.
 *
 * Identical GETs that start while an earlier request to the same URL is still
 * pending share the first promise instead of opening a second network request.
 * This stops StrictMode double-mounts and sibling components (e.g. two pages
 * both calling GET /api/v1/investigations on mount) from hammering the same
 * endpoint. POST/mutating calls are never shared.
 */
const inFlight = new Map<string, Promise<unknown>>();

function dedupKey(method: string, url: string): string {
  return `${method} ${url}`;
}

/** Build the final request URL from the path + query options. */
function buildUrl(path: string, query?: RequestOptions["query"]): string {
  let url = `${API_BASE}${path}`;
  if (query) {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== "") {
        params.append(k, String(v));
      }
    }
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }
  return url;
}

/** Perform a single fetch, honoring timeout + external abort signal. */
async function fetchOnce<T>(url: string, options: RequestOptions): Promise<T> {
  const { method = "GET", body, timeoutMs = 30000, headers, asBlob, signal } = options;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);

  // Bridge an external abort signal (component unmount/teardown) into the
  // per-request controller so aborted fetches are cut off at the network layer.
  const onExternalAbort = () => controller.abort();
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", onExternalAbort, { once: true });
  }

  try {
    const authToken = getToken();
    const res = await fetch(url, {
      method,
      headers: {
        Accept: "application/json",
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...headers,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });

    let data: unknown = null;
    if (res.ok && asBlob) {
      return { blob: await res.blob(), headers: res.headers } as T;
    }
    const text = await res.text();
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = text;
      }
    }

    if (!res.ok) {
      if (res.status === 401) {
        // The presented token is no longer valid. Discard it and let the
        // session provider prompt a clean re-login.
        clearToken();
        window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
      }
      const detail =
        typeof data === "object" && data !== null
          ? (data as ApiErrorBody).detail ?? (data as ApiErrorBody).message
          : undefined;
      throw new ApiError(userSafeMessage(res.status, typeof detail === "string" ? detail : undefined), {
        status: res.status,
        code: `http_${res.status}`,
      });
    }
    return data as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("The request timed out.", { code: "timeout", status: 408 });
    }
    logger.warn("API request failed", { url, method, error: String(err) });
    throw new ApiError("The service could not be reached. Check your connection and try again.", {
      code: "network",
    });
  } finally {
    if (signal) signal.removeEventListener("abort", onExternalAbort);
    window.clearTimeout(timer);
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", query } = options;
  const url = buildUrl(path, query);

  // De-duplicate in-flight GETs to the exact same URL so React.StrictMode's
  // double-mount and sibling components don't each fire a duplicate request.
  // The shared promise is cleared when it settles; aborting one caller only
  // cancels that caller's own subscription, never the shared fetch.
  if (method === "GET") {
    const key = dedupKey(method, url);
    const pending = inFlight.get(key);
    if (pending) return pending as Promise<T>;
    const started = fetchOnce<T>(url, options);
    inFlight.set(key, started);
    // Clear the shared slot when the request settles. `.then(ok, err)` (not
    // `.finally()`) so a failing GET doesn't leave an unhandled derived
    // rejection behind: both callbacks resolve the derived promise.
    void started.then(
      () => inFlight.delete(key),
      () => inFlight.delete(key),
    );
    return started;
  }
  return fetchOnce<T>(url, options);
}

export const client = {
  get: <T>(path: string, options?: RequestOptions) => request<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "POST", body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "PUT", body }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "PATCH", body }),
  del: <T>(path: string, options?: RequestOptions) => request<T>(path, { ...options, method: "DELETE" }),
  /** POST returning a Blob body (binary payloads like PDFs) plus response headers. */
  postBlob: <T = BlobResult>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "POST", body, asBlob: true }),
};
