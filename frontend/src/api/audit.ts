import { client } from "./client";
import { isDemoMode } from "./config";
import { getDemoAuditEvents } from "@/mock";
import type { AuditAction, AuditEvent } from "./types";

/**
 * Audit trail contract.
 *
 * Live mode reads the backend audit endpoint:
 *   GET /api/v1/audit?user=&action=&resource=&result=&from=&to=&limit=
 * Demo mode returns clearly-labeled synthetic events.
 */

export interface BackendAuditEventOut {
  id: string;
  timestamp: string;
  user: string;
  action: string;
  resource: string;
  resource_id: string;
  result: "success" | "denied" | "error";
  ip?: string | null;
}

export interface AuditEventsResponse {
  events: BackendAuditEventOut[];
  total: number;
  source: string;
}

const KNOWN_ACTIONS: AuditAction[] = [
  "VIEW",
  "CREATE",
  "UPDATE",
  "DELETE",
  "EXPORT",
  "LOGIN",
  "LOGOUT",
  "ANALYZE",
  "ATTRIBUTION_REQUEST",
];

export function mapBackendAuditEvent(e: BackendAuditEventOut): AuditEvent {
  const action = (KNOWN_ACTIONS as string[]).includes(e.action)
    ? (e.action as AuditAction)
    : "VIEW";
  return {
    id: e.id,
    timestamp: e.timestamp,
    user: e.user,
    action,
    resource: e.resource,
    resourceId: e.resource_id,
    ip: e.ip ?? undefined,
    result: e.result,
    isDemo: false,
  };
}

export interface AuditQueryOptions {
  user?: string;
  action?: string;
  resource?: string;
  result?: string;
  from?: string;
  to?: string;
  limit?: number;
}

export const audit = {
  async list(query: AuditQueryOptions = {}): Promise<AuditEvent[]> {
    if (isDemoMode()) return getDemoAuditEvents();
    const res = await client.get<AuditEventsResponse>("/api/v1/audit", {
      query: {
        user: query.user,
        action: query.action,
        resource: query.resource,
        result: query.result,
        ...(query.from ? { from: query.from } : {}),
        ...(query.to ? { to: query.to } : {}),
        limit: query.limit ?? 200,
      },
    });
    return (res.events ?? []).map(mapBackendAuditEvent);
  },
};