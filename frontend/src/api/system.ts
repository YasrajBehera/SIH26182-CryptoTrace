import { client } from "./client";

/**
 * Per-component availability, sourced from the authenticated
 * GET /api/v1/system/status endpoint. Each field is a plain boolean resolved
 * server-side at request time; the dashboard renders it honestly as
 * Connected / Not connected / Not available.
 */

export interface SystemStatus {
  backend: boolean;
  auth: boolean;
  postgres: boolean;
  blockchain: boolean;
  neo4j: boolean;
  graph: boolean;
  vasp: boolean;
  report: boolean;
  sahyog: boolean;
  /** True only when a production I4C/NCRP SAHYOG API is explicitly configured. */
  sahyog_production: boolean;
}

export const system = {
  /** Authenticated system status (requires a live session token). */
  async status(): Promise<SystemStatus> {
    return client.get<SystemStatus>("/api/v1/system/status", { timeoutMs: 10000 });
  },
};