import { useMemo, useState } from "react";
import { PageHeader, Button, Card, DemoBadge, Badge, Select, Input, RiskBadge, ShortAddress, EmptyState, LoadingBlock, SkeletonBlock } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { investigations } from "@/api/investigations";
import { useDataSource } from "@/app/DataSourceContext";
import { demoWalletSummaries } from "@/mock/activity";
import { RISK_ORDER } from "@/api/types";

export function RiskPage() {
  const { isDemo } = useDataSource();
  const { data: cases, loading, error, reload } = useApi((signal) => investigations.list(signal), []);

  const [level, setLevel] = useState("all");
  const [q, setQ] = useState("");

  const unanswered = useMemo(
    () => ({
      professional: cases?.filter((c) => c.risk === "critical" || c.risk === "high").length ?? 0,
      medium: cases?.filter((c) => c.risk === "medium").length ?? 0,
      low: cases?.filter((c) => c.risk === "low").length ?? 0,
      unknown: cases?.filter((c) => c.risk === "unknown").length ?? 0,
    }),
    [cases],
  );

  const highRiskWallets = useMemo(
    () => (isDemo ? Object.values(demoWalletSummaries).filter((w) => w.risk === "high" || w.risk === "critical") : []),
    [isDemo],
  );

  const visibleWallets = useMemo(() => {
    let list = highRiskWallets;
    if (level !== "all") list = list.filter((w) => w.risk === level);
    if (q) list = list.filter((w) => w.address.toLowerCase().includes(q.toLowerCase()));
    return list;
  }, [highRiskWallets, level, q]);

  return (
    <div className="page">
      <PageHeader
        title="Risk Analysis"
        subtitle="Investigation-level and wallet-level risk posture. Scores are advisory and derived from available signals."
        crumbs={[{ label: "Risk Analysis" }]}
        actions={isDemo ? <DemoBadge label="SYNTHETIC RISK METRICS" /> : undefined}
      />

      <div className="kpi-grid">
        <Card title="High / critical">
          <div style={{ fontSize: 26, fontWeight: 700 }}>{unanswered.professional}</div>
          <p style={{ margin: "4px 0 0", fontSize: "var(--text-xs)", color: "var(--text-faint)" }}>from case flags</p>
        </Card>
        <Card title="Medium">
          <div style={{ fontSize: 26, fontWeight: 700 }}>{unanswered.medium}</div>
          <p style={{ margin: "4px 0 0", fontSize: "var(--text-xs)", color: "var(--text-faint)" }}>from case flags</p>
        </Card>
        <Card title="Low">
          <div style={{ fontSize: 26, fontWeight: 700 }}>{unanswered.low}</div>
        </Card>
        <Card title="Unknown">
          <div style={{ fontSize: 26, fontWeight: 700 }}>{unanswered.unknown}</div>
          <p style={{ margin: "4px 0 0", fontSize: "var(--text-xs)", color: "var(--text-faint)" }}>
            no completed risk assessment attached
          </p>
        </Card>
      </div>

      <Card title="Risk posture by case" subtitle="Distribution of investigation-level risk flags.">
        {loading ? (
          <SkeletonBlock rows={4} />
        ) : error ? (
          <div className="stack">
            <p style={{ color: "var(--text-muted)" }}>{error}</p>
            <Button onClick={reload}>Retry</Button>
          </div>
        ) : (
          <div className="stack">
            {RISK_ORDER.map((level) => {
              const count = cases?.filter((c) => c.risk === level).length ?? 0;
              const total = cases?.length || 1;
              return (
                <div key={level} className="grid" style={{ gridTemplateColumns: "110px 1fr 44px", alignItems: "center", gap: 8 }}>
                  <RiskBadge level={level} />
                  <div className="confidence-bar">
                    <div
                      className="confidence-fill"
                      style={{
                        width: `${(count / total) * 100}%`,
                        background: level === "critical" ? "var(--red)" : level === "high" ? "var(--red)" : level === "medium" ? "var(--amber)" : level === "low" ? "var(--green)" : "var(--gray)",
                      }}
                    />
                  </div>
                  <span className="mono" style={{ textAlign: "right", color: "var(--text-muted)" }}>{count}</span>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <Card title="High-risk wallets" subtitle={isDemo ? "Synthetic flagged addresses for interface testing." : "Wallets with an attached analytical risk assessment. Risk scores are computed by the risk engine when an analysis is run."}>
        <div className="table-toolbar">
          <Select value={level} onChange={(e) => setLevel(e.target.value)} aria-label="Filter risk level" style={{ maxWidth: 160 }}>
            <option value="all">All risk levels</option>
            {RISK_ORDER.filter((r) => r === "high" || r === "critical").map((r) => (
              <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
            ))}
          </Select>
          <Input
            style={{ maxWidth: 260 }}
            placeholder="Filter by address…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Filter high-risk wallets by address"
          />
          <span className="spacer" />
          <Badge className="status-draft">{visibleWallets.length} flagged</Badge>
        </div>

        {loading ? (
          <LoadingBlock />
        ) : visibleWallets.length === 0 ? (
          <EmptyState
            title={isDemo ? "No flagged wallets" : "No assessed wallets"}
            description={isDemo ? "No demo wallets matched the current filter." : "No wallet has a completed risk assessment yet. Run an analysis on a wallet to compute its analytical risk — the risk engine derives scores from transfer volumes, counterparties, attribution candidates, and linked evidence."}
          />
        ) : (
          <table className="data-table" aria-label="High-risk wallets">
            <thead>
              <tr>
                <th>Address</th>
                <th>Network</th>
                <th>Risk</th>
                <th>Score</th>
                <th>First seen</th>
              </tr>
            </thead>
            <tbody>
              {visibleWallets.map((w) => (
                <tr key={w.address}>
                  <td><ShortAddress address={w.address} /></td>
                  <td><Badge>{w.network}</Badge></td>
                  <td><RiskBadge level={w.risk} /></td>
                  <td className="mono">{w.riskScore !== null && w.riskScore !== undefined ? w.riskScore : "unavailable"}</td>
                  <td>{w.firstSeen ? new Date(w.firstSeen).toLocaleDateString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <div className="risk-rule rr-high" role="note">
        <strong>Analytical risk assessment:</strong> the levels shown are risk indicators derived from case flags and
        wallet activity summaries. They are evidence-backed where wallet summaries or case assessments exist, and they
        <em> require investigator review before any action</em>. They are not confirmations of criminal activity or
        wallet ownership, and they are not a substitute for a dedicated sanctions-screening or enforcement-decision
        service.
      </div>
    </div>
  );
}