import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { PageHeader, Button, Card, Input, Select, DemoBadge, ErrorState, EmptyState, SkeletonBlock, Badge } from "@/components/ui";
import { AddIcon } from "@/components/icons";
import { useApi } from "@/hooks/useApi";
import { investigations } from "@/api/investigations";
import { isDemoMode } from "@/api/config";
import { InvestigationTable } from "@/components/investigations/InvestigationTable";
import { useAuth } from "@/auth/AuthContext";
import type { InvestigationStatus } from "@/api/types";

export function CasesPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { can } = useAuth();
  const { data, loading, error, reload } = useApi((signal) => investigations.list(signal), []);

  const [q, setQ] = useState("");
  const [status, setStatus] = useState<string>(params.get("status") ?? "all");

  const filtered = useMemo(
    () =>
      (data ?? []).filter((c) => {
        if (q) {
          const needle = q.toLowerCase();
          if (!`${c.id} ${c.name} ${c.description ?? ""} ${c.primaryWallet ?? ""}`.toLowerCase().includes(needle)) return false;
        }
        if (status !== "all" && c.status !== status) return false;
        return true;
      }),
    [data, q, status],
  );

  const countBy = (s: InvestigationStatus) => (data ?? []).filter((c) => c.status === s).length;

  return (
    <div className="page">
      <PageHeader
        title="Investigations"
        subtitle="Case management across the investigation lifecycle."
        crumbs={[{ label: "Investigations" }]}
        actions={
          can("investigation.create") ? (
            <Button variant="primary" leading={<AddIcon />} onClick={() => navigate("/cases/new")}>
              New Investigation
            </Button>
          ) : undefined
        }
      />

      <div className="table-toolbar">
        <DemoBadge label={isDemoMode() ? "DEMO CASES" : "LIVE"} />
        <Button variant="ghost" size="sm" onClick={reload}>
          ↻ Refresh
        </Button>
      </div>

      <Card>
        <div className="table-toolbar">
          <Input
            style={{ maxWidth: 280 }}
            placeholder="Search title, ID, subject…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Search investigations"
          />
          <Select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setParams(e.target.value === "all" ? {} : { status: e.target.value });
            }}
            aria-label="Filter by status"
            style={{ maxWidth: 180 }}
          >
            <option value="all">All statuses</option>
            {(["draft", "open", "investigating", "review", "closed"] as InvestigationStatus[]).map((s) => (
              <option key={s} value={s}>
                {s.charAt(0).toUpperCase() + s.slice(1)} ({countBy(s)})
              </option>
            ))}
          </Select>
          <span className="spacer" />
          <Badge className="status-draft">{filtered.length} shown</Badge>
        </div>

        {loading ? (
          <SkeletonBlock rows={8} />
        ) : error ? (
          <ErrorState title="Investigations are currently unavailable" description={error} action={<Button onClick={reload}>Retry</Button>} />
        ) : filtered.length === 0 ? (
          <EmptyState title="No investigations found" description="Adjust filters or create a new investigation." />
        ) : (
          <InvestigationTable investigations={filtered} pagination={{ pageSize: 10 }} />
        )}
      </Card>
    </div>
  );
}