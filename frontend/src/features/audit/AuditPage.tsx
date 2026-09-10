import { useMemo, useState } from "react";
import { PageHeader, Button, Card, DemoBadge, Badge, Input, Select, LoadingBlock, ErrorState } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { audit } from "@/api/evidence";
import { useDataSource } from "@/app/DataSourceContext";
import { useAuth } from "@/auth/AuthContext";
import { formatDate } from "@/lib/format";
import type { AuditAction, AuditEvent } from "@/api/types";

const ACCOUNTABILITY_NOTICE =
  "Every screen interaction that reads or writes case data should be recorded here once an audit backend ships. This log is labeled demo data today.";

export function AuditPage() {
  const { isDemo } = useDataSource();
  const { can } = useAuth();
  const { data, loading, error, reload } = useApi(() => audit.list(), []);

  const [q, setQ] = useState("");
  const [action, setAction] = useState("all");
  const [result, setResult] = useState("all");

  const actions: AuditAction[] = ["VIEW", "CREATE", "UPDATE", "DELETE", "EXPORT", "LOGIN", "LOGOUT", "ANALYZE", "ATTRIBUTION_REQUEST"];

  const filtered = useMemo(
    () =>
      (data ?? []).filter((e) => {
        if (q) {
          const needle = q.toLowerCase();
          if (!`${e.user} ${e.resource} ${e.resourceId} ${e.ip ?? ""}`.toLowerCase().includes(needle)) return false;
        }
        if (action !== "all" && e.action !== action) return false;
        if (result !== "all" && e.result !== result) return false;
        return true;
      }),
    [data, q, action, result],
  );

  if (!can("audit.read")) {
    return (
      <div className="page">
        <PageHeader title="Audit Logs" />
        <Card>
          <p style={{ color: "var(--text-muted)" }}>Your role does not permit viewing the audit log.</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        title="Audit Logs"
        subtitle="Accountability trail for investigator actions. Demo records until an audit backend ships."
        crumbs={[{ label: "Audit Logs" }]}
        actions={isDemo ? <DemoBadge label="DEMO AUDIT TRAIL" /> : undefined}
      />

      <div className="risk-rule rr-low" role="note">{ACCOUNTABILITY_NOTICE}</div>

      <Card>
        <div className="table-toolbar">
          <Input
            style={{ maxWidth: 240 }}
            placeholder="Search user, resource…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Search audit log"
          />
          <Select value={action} onChange={(e) => setAction(e.target.value)} aria-label="Filter by action" style={{ maxWidth: 170 }}>
            <option value="all">All actions</option>
            {actions.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </Select>
          <Select value={result} onChange={(e) => setResult(e.target.value)} aria-label="Filter by result" style={{ maxWidth: 150 }}>
            <option value="all">All results</option>
            <option value="success">Success</option>
            <option value="denied">Denied</option>
            <option value="error">Error</option>
          </Select>
          <span className="spacer" />
          <Badge className="status-draft">{filtered.length} events</Badge>
          <Button variant="ghost" size="sm" onClick={reload}>
            ↻ Refresh
          </Button>
        </div>

        {loading ? (
          <LoadingBlock />
        ) : error ? (
          <ErrorState title="Audit log is currently unavailable" description={error} action={<Button onClick={reload}>Retry</Button>} />
        ) : filtered.length === 0 ? (
          <p style={{ color: "var(--text-faint)", textAlign: "center", padding: "var(--space-6)" }}>
            No audit events match the current filters.
          </p>
        ) : (
          <table className="data-table" aria-label="Audit events">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>User</th>
                <th>Action</th>
                <th>Resource</th>
                <th>ID</th>
                <th>Result</th>
                <th>IP</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((e: AuditEvent) => (
                <tr key={e.id}>
                  <td title={e.timestamp}>{formatDate(e.timestamp)}</td>
                  <td>{e.user}</td>
                  <td>
                    <Badge className={e.action === "DELETE" ? "risk-critical" : e.action === "EXPORT" ? "status-investigating" : "status-open"}>
                      {e.action}
                    </Badge>
                  </td>
                  <td>{e.resource}</td>
                  <td className="mono" style={{ fontSize: 12 }}>{e.resourceId}</td>
                  <td>
                    <Badge className={e.result === "success" ? "status-success" : e.result === "denied" ? "risk-critical" : "status-escalated"}>
                      {e.result}
                    </Badge>
                  </td>
                  <td className="mono" style={{ fontSize: 12 }}>{e.ip ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}