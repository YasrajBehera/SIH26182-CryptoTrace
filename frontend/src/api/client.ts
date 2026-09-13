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

export const API_BASE = ""; // same origin; vite proxy handles /api

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
}

export interface BlobResult {
  blob: Blob;
  headers: Headers;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query, timeoutMs = 30000, headers, asBlob } = options;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);

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
    logger.warn("API request failed", { path, method, error: String(err) });
    throw new ApiError("The service could not be reached. Check your connection and try again.", {
      code: "network",
    });
  } finally {
    window.clearTimeout(timer);
  }
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