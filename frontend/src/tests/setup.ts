import "@testing-library/jest-dom";
import { vi } from "vitest";

/**
 * Shared test setup. jsdom + Vitest + Node's undici `fetch`.
 *
 * Under the jsdom environment, `AbortController`/`AbortSignal` resolve to
 * jsdom's implementations while `fetch` is Node/undici, which rejects any
 * signal that is not a native undici `AbortSignal`:
 *
 *   "TypeError: RequestInit: Expected signal to be an instance of AbortSignal."
 *
 * That mismatch never occurs in the browser (a page pairs its own `fetch`
 * with its own `AbortController`), so the production client is not patched.
 * Instead `fetch` is stubbed to deterministically report the backend as
 * unreachable (503). `DataSourceProvider` turns that into the honest
 * "demo mode" state the dashboard tests assert, and every suite stays
 * deterministic and offline.
 */

const unavailable = {
  ok: false,
  status: 503,
  statusText: "Service Unavailable",
  text: async () => JSON.stringify({ detail: "Backend not running in test environment" }),
} as unknown as Response;

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async () => unavailable));
});

afterEach(() => {
  vi.unstubAllGlobals();
});