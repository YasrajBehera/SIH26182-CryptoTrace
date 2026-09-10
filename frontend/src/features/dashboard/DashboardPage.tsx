import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageHeader, Button, MetricCard, Card, Timeline, DemoBadge, Badge, Input, Select, EmptyState } from "@/components/ui";
import { AddIcon, WalletIcon, ExportIcon, RiskIcon } from "@/components/icons";
import { useApi } from "@/hooks/useApi";
import { investigations, activity } from "@/api/investigations";
import { evidence } from "@/api/evidence";
import { attribution } from "@/api/attribution";
import { graph } from "@/api/graph";
import { useDataSource } from "@/app/DataSourceContext";
import { useAuth } from "@/auth/AuthContext";
import { InvestigationTable } from "@/components/investigations/InvestigationTable";
import { InvestigationWorkflow } from "@/components/investigations/InvestigationWorkflow";
import { RiskBarChart } from "@/components/ui/Charts";
import { FundFlowDiagram } from "@/components/graph/FundFlowDiagram";
import type { RiskLevel, AttributionState } from "@/api/types";
import { RISK_ORDER } from "@/api/types";
import { WalletQuickLook } from "@/components/wallets/WalletQuickLook";
import { isDemoMode } from "@/api/config";
import { formatDate } from "@/lib/format";

const RISK_EXPLANATION: Record<RiskLevel, string> = {
  critical: "Immediate exposure — escalate and triage first.",
  high: "Elevated exposure — prioritize flow tracing.",
  medium: "Moderate exposure — monitor supporting evidence.",
  low: "Limited exposure — routine monitoring.",
  unknown: "No scoring available until the risk engine ships.",
};

const VASP_STATE_LABEL: Record<AttributionState, string> = {
  not_analyzed: "Not analyzed",
  analysis_pending: "Analysis pending",
  no_attribution: "No attribution found",
  candidate_detected: "Candidate",
  evidence_insufficient: "Insufficient Evidence",
  high_confidence: "Evidence Supported",
  medium_confidence: "Evidence Supported",
  low_confidence: "Candidate",
};

const VASP_STATE_CLASS: Record<AttributionState, string> = {
  not_analyzed: "status-draft",
  analysis_pending: "status-pending",
  no_attribution: "status-draft",
  candidate_detected: "status-open",
  evidence_insufficient: "status-pending",
  high_confidence: "status-success",
  medium_confidence: "status-success",
  low_confidence: "status-open",
};

function prettyLabel(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c: string) => c.toUpperCase());
}

export function DashboardPage() {
  const navigate = useNavigate();
  const { mode } = useDataSource();
  const { can } = useAuth();
  const demo = isDemoMode();

  const { data: cases, loading: casesLoading, error: casesError, reload: reloadCases } = useApi(() => investigations.list(), []);
  const { data: feed } = useApi(() => activity.feed(), []);
  const { data: evidenceItems } = useApi(() => evidence.list(), []);
  const { data: candidates } = useApi(() => attribution.candidates(), []);
  const { data: flowPath } = useApi(
    () => graph.path("0xdemo0", "0xdemoLeaf"),
    [],
    { enabled: demo },
  );

  // Investigation control bar — these filters genuinely narrow the data below.
  const [q, setQ] = useState("");
  const [riskFilter, setRiskFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [networkFilter, setNetworkFilter] = useState("all");
  const [withinDays, setWithinDays] = useState("all");

  const filteredCases = useMemo(() => {
    const list = cases ?? [];
    const now = Date.now();
    const within = withinDays === "all" ? null : Number(withinDays) * 24 * 3600_000;
    return list.filter((c) => {
      if (q) {
        const hay = `${c.id} ${c.name} ${c.primaryWallet} ${c.assignedAnalyst} ${c.tags.join(" ")}`.toLowerCase();
        if (!hay.includes(q.toLowerCase())) return false;
      }
      if (riskFilter !== "all" && c.risk !== riskFilter) return false;
      if (statusFilter !== "all" && c.status !== statusFilter) return false;
      if (networkFilter !== "all" && c.network !== networkFilter) return false;
      if (within !== null && now - new Date(c.updatedAt).getTime() > within) return false;
      return true;
    });
  }, [cases, q, riskFilter, statusFilter, networkFilter, withinDays]);

  const activeCases = useMemo(
    () => filteredCases.filter((c) => c.status === "open" || c.status === "investigating" || c.status === "escalated"),
    [filteredCases],
  );

  const networks = useMemo(
    () => Array.from(new Set((cases ?? []).map((c) => c.network))).sort(),
    [cases],
  );

  const stats = useMemo(() => {
    return {
      totalInvestigations: cases?.length ?? 0,
      activeInvestigations: activeCases.length,
      walletsAnalyzed: demo ? 1286 : null,
      transactionsTraced: demo ? (cases ?? []).reduce((a, c) => a + c.transactions, 0) : null,
      highRiskWallets: demo ? 47 : null,
      vaspCandidates: candidates?.length ?? 0,
      evidenceItems: evidenceItems?.length ?? 0,
      openAlerts: demo ? 6 : null,
      demo,
    };
  }, [cases, activeCases, candidates, evidenceItems, demo]);

  const riskCounts = useMemo(() => {
    const counts = new Map<RiskLevel, number>();
    RISK_ORDER.forEach((r) => counts.set(r, 0));
    filteredCases.forEach((c) => counts.set(c.risk, (counts.get(c.risk) ?? 0) + 1));
    return RISK_ORDER.map((level) => ({ level, count: counts.get(level) ?? 0 }));
  }, [filteredCases]);

  const riskTotal = riskCounts.reduce((a, c) => a + c.count, 0);

  const recentEvidence = evidenceItems?.slice(0, 5) ?? [];
  const recentCandidates = candidates?.slice(0, 4) ?? [];

  return (
    <div className="page">
      <PageHeader
        title="Investigation Overview"
        subtitle="Trace wallets, map transaction flows, attribute service providers, and build evidence — from unknown wallet to investigation report."
        crumbs={[{ label: "Overview" }]}
        actions={
          <>
            {can("investigation.create") ? (
              <Button variant="primary" leading={<AddIcon />} onClick={() => navigate("/investigations?new=1")}>
                New Investigation
              </Button>
            ) : null}
            {can("wallet.analyze") ? (
              <Button leading={<WalletIcon />} onClick={() => navigate("/wallets")}>
                Investigate Wallet
              </Button>
            ) : null}
            {can("report.export") ? (
              <Button leading={<ExportIcon />} onClick={() => navigate("/reports")}>
                Export Report
              </Button>
            ) : null}
          </>
        }
      />

      {/* Investigation workflow pipeline */}
      <Card title="Investigation workflow" subtitle="Every trace follows the same evidence-first pipeline — from unknown wallet to documented report.">
        <InvestigationWorkflow active={-1} />
      </Card>

      {/* Top metrics */}
      <div className="kpi-grid">
        <MetricCard label="Active Investigations" value={stats.activeInvestigations} desc={demo ? "DEMO — cases open/in progress/escalated" : "Cases open or in progress"} awaiting={!demo && stats.activeInvestigations === 0} />
        <MetricCard label="Total Investigations" value={stats.totalInvestigations} desc="All cases in the workspace" awaiting={!demo && stats.totalInvestigations === 0} />
        <MetricCard
          label="Wallets Analyzed"
          value={stats.walletsAnalyzed}
          desc={demo ? "DEMO — synthetic aggregate" : "Derived from backend summary endpoint"}
          awaiting={!demo}
        />
        <MetricCard
          label="Transactions Traced"
          value={stats.transactionsTraced?.toLocaleString()}
          desc={demo ? "DEMO — aggregated from synthetic cases" : "Derived from backend summary endpoint"}
          awaiting={!demo}
        />
        <MetricCard
          label="VASP Candidates"
          value={stats.vaspCandidates}
          desc={demo ? "DEMO — candidate associations only" : "Requires Member 3 engine"}
          awaiting={!demo && stats.vaspCandidates === 0}
        />
        <MetricCard
          label="High-Risk Wallets"
          value={stats.highRiskWallets}
          risk="high"
          desc={demo ? "DEMO — demo flag count" : "Requires backend risk engine"}
          awaiting={!demo}
        />
        <MetricCard
          label="Evidence Items"
          value={stats.evidenceItems}
          desc={demo ? "DEMO — synthetic evidence" : "Requires Member 3 engine"}
          awaiting={!demo && stats.evidenceItems === 0}
        />
        <MetricCard
          label="Open Alerts"
          value={stats.openAlerts}
          risk="critical"
          desc={demo ? "DEMO — alert count" : "Requires alerting backend"}
          awaiting={!demo}
        />
      </div>

      {demo ? (
        <div>
          <DemoBadge label="DEMO METRICS — synthetic numbers, not production telemetry" />
        </div>
      ) : null}

      {/* System status + risk intelligence + fund flow preview */}
      <div className="grid grid-3">
        <Card title="System Status" subtitle="Honest availability of each engine">
          <div className="stack">
            <StatusRow
              label="Blockchain ingestion API"
              detail="GET /api/v1/wallets/{address}/transfers"
              tone={mode === "live" ? "ok" : "warn"}
              state={mode === "live" ? "Live" : "Unavailable"}
            />
            <StatusRow
              label="API Health probe"
              detail="GET /api/v1/health"
              tone={mode === "live" ? "ok" : "error"}
              state={mode === "live" ? "Connected" : "Not reachable — demo mode"}
            />
            <StatusRow
              label="Database (cases / evidence)"
              detail="Investigation persistence"
              tone="warn"
              state="Not connected"
            />
            <StatusRow
              label="Analysis engine (graph)"
              detail="Member 2 — Neo4j graph"
              tone="warn"
              state="Not available"
            />
            <StatusRow
              label="Attribution engine (VASP)"
              detail="Member 3 — intelligence"
              tone="warn"
              state="Not available"
            />
            <StatusRow
              label="Report service (PDF)"
              detail="Server-side export"
              tone="warn"
              state="Not connected"
            />
          </div>
        </Card>

        <Card
          title="Risk Intelligence"
          subtitle={riskTotal ? "Distribution across the filtered investigation set" : "No data — awaiting backend"}
        >
          {riskTotal ? (
            <div className="stack">
              <RiskBarChart data={riskCounts} total={riskTotal} testid="risk-bar-chart" />
              <div className="divider" />
              <div className="stack" style={{ gap: 6 }}>
                {riskCounts
                  .filter((r) => r.count > 0)
                  .map((r) => (
                    <div key={r.level} className="row" style={{ gap: 8, alignItems: "flex-start" }}>
                      <RiskIcon />
                      <span style={{ fontSize: "var(--text-sm)" }}>
                        <strong className={`conf-level conf-unavailable`}>{r.level.charAt(0).toUpperCase() + r.level.slice(1)}</strong>{" "}
                        <span className="text-dim">{RISK_EXPLANATION[r.level]}</span>
                      </span>
                    </div>
                  ))}
              </div>
            </div>
          ) : (
            <div className="text-dim" style={{ fontSize: "var(--text-sm)" }}>
              Risk classification is not computed until the backend provides investigations with risk levels.
            </div>
          )}
        </Card>

        <Card
          title="Fund Flow Preview"
          subtitle={demo ? "DEMO — synthetic path, not computed from chain data" : "Requires Member 2 graph engine"}
          actions={
            <Button variant="ghost" size="sm" onClick={() => navigate("/graph?tab=flow")}>
              Open in graph →
            </Button>
          }
        >
          {demo && flowPath ? (
            <FundFlowDiagram path={flowPath} demo onNodeClick={(n) => navigate(`/graph?address=${encodeURIComponent(n.address)}`)} />
          ) : (
            <div className="text-dim" style={{ fontSize: "var(--text-sm)" }}>
              Fund-flow reconstruction becomes available when the Member 2 graph engine ships. No live graph data is
              shown.
            </div>
          )}
        </Card>
      </div>

      {/* Investigation control bar */}
      <Card
        title="Active Investigations"
        subtitle={`${activeCases.length} of ${filteredCases.length} shown after filters`}
        actions={
          <span className="row" style={{ gap: 6 }}>
            <Button variant="ghost" size="sm" onClick={reloadCases}>↻ Refresh</Button>
            <Button variant="ghost" size="sm" onClick={() => navigate("/investigations")}>
              View all →
            </Button>
          </span>
        }
      >
        <div className="investigation-controls" role="group" aria-label="Investigation filters">
          <Input
            className="mono"
            style={{ maxWidth: 260 }}
            placeholder="Filter by case, wallet, or analyst…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Search investigations"
          />
          <Select value={networkFilter} onChange={(e) => setNetworkFilter(e.target.value)} aria-label="Network" style={{ maxWidth: 150 }}>
            <option value="all">All networks</option>
            {networks.map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </Select>
          <Select value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)} aria-label="Risk level" style={{ maxWidth: 150 }}>
            <option value="all">All risk</option>
            {RISK_ORDER.map((r) => (
              <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
            ))}
          </Select>
          <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label="Status" style={{ maxWidth: 170 }}>
            <option value="all">All statuses</option>
            <option value="open">Open</option>
            <option value="investigating">Investigating</option>
            <option value="escalated">Escalated</option>
            <option value="review">Pending review</option>
            <option value="closed">Closed</option>
            <option value="draft">Draft</option>
          </Select>
          <Select value={withinDays} onChange={(e) => setWithinDays(e.target.value)} aria-label="Updated within" style={{ maxWidth: 170 }}>
            <option value="all">Any update time</option>
            <option value="7">Updated in 7 days</option>
            <option value="30">Updated in 30 days</option>
            <option value="90">Updated in 90 days</option>
          </Select>
          {(q || riskFilter !== "all" || statusFilter !== "all" || networkFilter !== "all" || withinDays !== "all") ? (
            <Button variant="ghost" size="sm" onClick={() => { setQ(""); setRiskFilter("all"); setStatusFilter("all"); setNetworkFilter("all"); setWithinDays("all"); }}>
              Clear filters
            </Button>
          ) : null}
        </div>

        {casesLoading ? (
          <div className="state" role="status"><span className="inline-spinner" aria-hidden /><p className="state-desc">Loading investigations…</p></div>
        ) : casesError ? (
          <div className="stack">
            <p style={{ color: "var(--text-muted)" }}>{casesError}</p>
            <Button onClick={reloadCases}>Retry</Button>
          </div>
        ) : filteredCases.length === 0 ? (
          <EmptyState
            title="No matching investigations"
            description="Adjust or clear the filters, or create a new investigation to begin tracing."
          />
        ) : (
          <InvestigationTable investigations={activeCases.length ? activeCases : filteredCases} pagination={{ pageSize: 6 }} />
        )}
      </Card>

      {/* Activity + evidence + VASP snapshots */}
      <div className="grid grid-3">
        <Card
          title="Recent Investigation Activity"
          subtitle="Timeline of events across cases"
          actions={
            <Button variant="ghost" size="sm" onClick={() => navigate("/audit")}>
              Audit log →
            </Button>
          }
        >
          <Timeline events={feed ?? []} max={6} />
          {!feed?.length ? <p className="text-dim" style={{ fontSize: "var(--text-sm)" }}>No recent activity.</p> : null}
        </Card>

        <Card
          title="Evidence Snapshot"
          subtitle={recentEvidence.length ? "Most recent evidence items" : "No evidence items"}
          actions={
            <Button variant="ghost" size="sm" onClick={() => navigate("/evidence")}>
              Evidence →
            </Button>
          }
        >
          {recentEvidence.length ? (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Evidence ID</th>
                    <th scope="col">Type</th>
                    <th scope="col">Source</th>
                    <th scope="col">Reliability</th>
                    <th scope="col">Related Wallet</th>
                    <th scope="col">Related Tx</th>
                    <th scope="col">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {recentEvidence.map((e) => (
                    <tr key={e.id} className="clickable" onClick={() => navigate(`/evidence?focus=${encodeURIComponent(e.id)}`)}>
                      <td><strong>{e.id}</strong></td>
                      <td>{prettyLabel(e.type)}</td>
                      <td>{e.source}</td>
                      <td>
                        <Badge className={e.reliability === "verified" || e.reliability === "high" ? "status-success" : e.reliability === "medium" ? "status-pending" : "status-draft"}>
                          {e.reliability}
                        </Badge>
                      </td>
                      <td className="mono">{e.relatedWallet ? e.relatedWallet.slice(0, 8) : "—"}…</td>
                      <td className="mono">{e.relatedTransaction ? e.relatedTransaction.slice(0, 10) : "—"}</td>
                      <td>{formatDate(e.createdAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-dim" style={{ fontSize: "var(--text-sm)" }}>
              Evidence accumulates once the Member 3 evidence service is connected.
            </p>
          )}
        </Card>

        <Card
          title="VASP Intelligence"
          subtitle={recentCandidates.length ? "Potential associations — not verified ownership" : "No candidates"}
          actions={
            <Button variant="ghost" size="sm" onClick={() => navigate("/vasp")}>
              VASP × <span style={{ color: "var(--cyan)" }}>→</span>
            </Button>
          }
        >
          {recentCandidates.length ? (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Candidate</th>
                    <th scope="col">Confidence</th>
                    <th scope="col">Evidence</th>
                    <th scope="col">Related Addresses</th>
                    <th scope="col">Transaction Volume</th>
                    <th scope="col">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {recentCandidates.map((c) => (
                    <tr key={c.id} className="clickable" onClick={() => navigate(`/vasp?wallet=${encodeURIComponent(c.wallet)}`)}>
                      <td>
                        <span className="row" style={{ gap: 6 }}>
                          <span
                            className="status-dot"
                            style={{ background: c.confidenceLevel === "high" ? "var(--green)" : c.confidenceLevel === "medium" ? "var(--amber)" : c.confidenceLevel === "low" ? "var(--gray)" : "var(--gray)" }}
                            aria-hidden
                          />
                          <strong>{c.vaspName}</strong>
                        </span>
                      </td>
                      <td>
                        {c.confidenceScore !== null && c.confidenceScore !== undefined ? (
                          `${c.confidenceScore}%`
                        ) : (
                          <span className="text-dim">unavailable</span>
                        )}
                      </td>
                      <td>{c.evidenceCount} items</td>
                      <td className="mono">{c.relatedAddresses.length > 0 ? c.relatedAddresses.slice(0, 2).map((a) => `${a.slice(0, 6)}…`).join(", ") : "—"}</td>
                      <td className="mono">{c.transactionVolume} {c.asset}</td>
                      <td>
                        <Badge className={VASP_STATE_CLASS[c.state]}>{VASP_STATE_LABEL[c.state]}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-dim" style={{ fontSize: "var(--text-sm)" }}>
              Candidate associations appear once the Member 3 attribution engine is connected.
            </p>
          )}
        </Card>
      </div>

      {/* Wallet lookup */}
      <Card title="Quick Wallet Lookup" subtitle="Investigate any public Ethereum address">
        <WalletQuickLook />
      </Card>
    </div>
  );
}

function StatusRow({
  label,
  detail,
  tone,
  state,
}: {
  label: string;
  detail: string;
  tone: "ok" | "warn" | "error";
  state: string;
}) {
  return (
    <div className="sidebar-status">
      <span className={`status-dot ${tone}`} aria-hidden />
      <span>
        <strong>{label}</strong>
        <span style={{ display: "block", color: "var(--text-faint)", fontSize: "var(--text-xs)" }}>{detail}</span>
      </span>
      <span className="status-state" style={{ marginLeft: "auto", fontSize: "var(--text-xs)", color: tone === "ok" ? "var(--green)" : tone === "warn" ? "var(--amber)" : "var(--red)" }}>
        {state}
      </span>
    </div>
  );
}