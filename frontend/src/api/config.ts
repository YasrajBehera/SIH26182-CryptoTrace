/**
 * Data-source configuration.
 *
 * The frontend can run in two modes:
 *  - "live": talks to the FastAPI backend (Member 1). Used once backend health
 *    is confirmed.
 *  - "demo": falls back to clearly-labeled synthetic data for features whose
 *    backend does not exist yet (graph, attribution, evidence, cases, reports,
 *    audit) and for wallet transfers when the backend is unreachable.
 *
 * Every synthetic record is flagged with `isDemo: true`, and the UI shows a
 * persistent DEMO DATA banner whenever this mode is active.
 */

export type DataSource = "live" | "demo";

export const DATA_SOURCE_KEY = "cryptotrace.dataSource";

let current: DataSource = "demo";

export function getDataSource(): DataSource {
  return current;
}

export function setDataSource(mode: DataSource): void {
  current = mode;
}

export function isDemoMode(): boolean {
  return current === "demo";
}

/** Hydrate initial mode from settings store (auto-negotiated by App on boot). */
export function initDataSource(mode: DataSource): void {
  current = mode;
}