import { useCallback, useEffect, useMemo, useState, Fragment } from "react";
import { PageHeader, Button, MetricCard, Card, DemoBadge, Badge, Input, Select, useToast } from "@/components/ui";
import { useDataSource } from "@/app/DataSourceContext";
import { useAuth } from "@/auth/AuthContext";
import { sahyog } from "@/api/sahyog";
import { createDemoReferrals, type SahyogReferral } from "@/mock/sahyog";
import { formatDate } from "@/lib/format";
import type { SahyogReferralView } from "@/api/types";

const PIPELINE = [
  { label: "Complaint Received", desc: "I4C / NCRP referral intake" },
  { label: "Wallet Triage", desc: "Risk flags, age, exchange exposure" },
  { label: "Investigate", desc: "Hand off to CryptoTrace case" },
] as const;

const RISK_BADGE: Record<string, string> = { high: "risk-critical", medium: "status-open", low: "status-success" };
const STATUS_BADGE: Record<string, string> = { new: "status-draft", triaged: "status-pending", handed_off: "status-success" };
const STATUS_LABEL: Record<string, string> = { new: "New", triaged: "Triaged", handed_off: "Handed Off" };

function triageReferral(r: SahyogReferral): SahyogReferral["triage"] {
  const riskScore =
    (r.amountUSDT > 50000 ? 2 : r.amountUSDT > 5000 ? 1 : 0) +
    (r.amountUSDT > 10000 ? 1 : 0);
  const risk = riskScore >= 3 ? "high" : riskScore >= 1 ? "medium" : "low";
  return {
    risk,
    walletAgeMonths: r.amountUSDT > 10000 ? 1 : 18,
    exchangeExposed: r.amountUSDT > 20000,
    priorFlags: risk === "high" ? 3 : risk === "medium" ? 1 : 0,
    recommendation: risk === "high" ? "investigate" : risk === "medium" ? "monitor" : "watchlist",
    triagedBy: "Current User",
    triagedAt: new Date().toISOString(),
  };
}

function updatedRiskPriority(r: SahyogReferralView): string {
  const level = r.triage?.risk ?? "low";
  if (level === "high") return "critical";
  if (level === "medium") return "high";
  return "normal";
}

export function SahyogPage() {
  const { isDemo } = useDataSource();
  const { can } = useAuth();
  const { push } = useToast();
  const [referrals, setReferrals] = useState<SahyogReferralView[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  const [q, setQ] = useState("");

  const reload = useCallback(async () => {
    if (isDemo) {
      setReferrals(createDemoReferrals());
      setLoadError(null);
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      setReferrals(await sahyog.list());
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "The referral queue is currently unavailable.");
    } finally {
      setLoading(false);
    }
  }, [isDemo]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const filtered = useMemo(() => {
    return referrals.filter((r) => {
      if (filter !== "all" && r.status !== filter) return false;
      if (q) {
        const needle = q.toLowerCase();
        if (
          !`${r.firNo} ${r.victimName} ${r.suspectWallet} ${r.id}`.toLowerCase().includes(needle)
        )
          return false;
      }
      return true;
    });
  }, [referrals, filter, q]);

  const counts = useMemo(() => {
    const n = { total: referrals.length, new: 0, triaged: 0, handed_off: 0 };
    referrals.forEach((r) => n[r.status]++);
    return n;
  }, [referrals]);

  async function handleTriage(id: string) {
    const referral = referrals.find((r) => r.id === id);
    if (!referral || referral.status !== "new") return;
    if (isDemo) {
      setReferrals((prev) =>
        prev.map((r) =>
          r.id === id && r.status === "new"
            ? { ...r, status: "triaged" as const, triage: triageReferral(r) }
            : r,
        ),
      );
      setExpandedId(id);
      return;
    }
    try {
      const updated = await sahyog.triage(id);
      setReferrals((prev) => prev.map((r) => (r.id === id ? updated : r)));
      setExpandedId(id);
      push({ kind: "ok", title: "Referral triaged", description: "Risk verdict computed by the backend SAHYOG module (DEMO)." });
    } catch (err) {
      push({ kind: "error", title: "Triage failed", description: err instanceof Error ? err.message : "Unknown error." });
    }
  }

  async function handleHandoff(id: string) {
    const referral = referrals.find((r) => r.id === id);
    if (!referral || referral.status !== "triaged") return;
    if (isDemo) {
      const caseId = `CT-2026-${String(150 + Math.floor(Math.random() * 99)).padStart(4, "0")}`;
      setReferrals((prev) =>
        prev.map((r) =>
          r.id === id && r.status === "triaged"
            ? { ...r, status: "handed_off" as const, handoffCaseId: caseId }
            : r,
        ),
      );
      return;
    }
    try {
      const updated = await sahyog.handoff(id, {
        caseName: `SAHYOG handoff ${referral.firNo}`,
        description: `Referral ${referral.id} (${referral.victimName}) handed off from the SAHYOG DEMO intake.`,
        priority: updatedRiskPriority(referral),
      });
      setReferrals((prev) => prev.map((r) => (r.id === id ? updated : r)));
      push({ kind: "ok", title: "Investigation created", description: `Case ${updated.handoffCaseId} created for this referral.` });
    } catch (err) {
      push({ kind: "error", title: "Handoff failed", description: err instanceof Error ? err.message : "Unknown error." });
    }
  }

  if (!can("wallet.analyze")) {
    return (
      <div className="page">
        <PageHeader title="SAHYOG Referral Intake" />
        <Card>
          <p style={{ color: "var(--text-muted)" }}>
            Your role does not permit viewing SAHYOG referrals. This module is for investigators who perform suspect-wallet triage.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        title="SAHYOG Referral Intake"
        subtitle="I4C Sahyog cybercrime-referral flow: victim complaint → suspect-wallet triage → CryptoTrace investigation handoff (DEMO)."
        crumbs={[{ label: "SAHYOG" }]}
        actions={isDemo ? <DemoBadge label="SYNTHETIC REFERRALS" /> : <Badge className="status-draft">DEMO flow</Badge>}
      />

      <div className="risk-rule rr-low" role="note">
        <strong>DEMO INTEGRATION:</strong> No live I4C/NCRP connection is used. Referral intake is
        simulated end-to-end by the backend SAHYOG module; every record is synthetic and clearly marked.
      </div>

      {/* Pipeline visualization */}
      <Card title="Referral Pipeline" subtitle="End-to-end flow from complaint intake to investigation handoff.">
        <div className="sahyog-pipeline" style={{ display: "flex", gap: "var(--space-4)", alignItems: "center" }}>
          {PIPELINE.map((step, i) => (
            <Fragment key={step.label}>
              <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: "50%",
                    background: "var(--surface-2)",
                    border: "2px solid var(--border)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontWeight: 700,
                    fontSize: 14,
                    color: "var(--cyan)",
                  }}
                >
                  {i + 1}
                </div>
                <span style={{ fontWeight: 600, fontSize: "var(--text-sm)", textAlign: "center" }}>{step.label}</span>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)", textAlign: "center" }}>{step.desc}</span>
              </div>
              {i < PIPELINE.length - 1 ? (
                <span style={{ color: "var(--text-faint)", fontSize: 18, flex: "0 0 auto" }} aria-hidden>→</span>
              ) : null}
            </Fragment>
          ))}
        </div>
      </Card>

      {/* Metrics */}
      <div className="kpi-grid">
        <MetricCard label="Total Referrals" value={counts.total} desc="Mock I4C Sahyog intake" />
        <MetricCard label="Awaiting Triage" value={counts.new} risk={counts.new > 0 ? "high" : undefined} desc="Unprocessed complaints" />
        <MetricCard label="Triaged" value={counts.triaged} desc="Risk-assessed, awaiting handoff" />
        <MetricCard label="Handed Off" value={counts.handed_off} desc="Assigned to CryptoTrace case" />
      </div>

      {isDemo ? (
        <div>
          <DemoBadge label="DEMO REFERRALS — synthetic complaint data, not real I4C feed" />
        </div>
      ) : null}

      {/* Referral table */}
      <Card
        title="Referral Queue"
        subtitle={`${filtered.length} of ${referrals.length} shown`}
        actions={
          <div style={{ display: "flex", gap: 6 }}>
            <Input
              style={{ maxWidth: 220 }}
              placeholder="Search FIR, wallet…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              aria-label="Search referrals"
            />
            <Select value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter by status" style={{ maxWidth: 150 }}>
              <option value="all">All statuses</option>
              <option value="new">New</option>
              <option value="triaged">Triaged</option>
              <option value="handed_off">Handed Off</option>
            </Select>
          </div>
        }
      >
        {loadError ? (
          <p style={{ color: "var(--text-muted)", margin: "0 0 var(--space-3)" }}>
            {loadError} <Button size="sm" variant="ghost" onClick={() => void reload()}>Retry</Button>
          </p>
        ) : null}
        {loading && referrals.length === 0 ? (
          <p style={{ color: "var(--text-faint)", textAlign: "center", padding: "var(--space-5)" }}>
            Loading referrals…
          </p>
        ) : null}
        <table className="data-table" aria-label="SAHYOG referrals">
          <thead>
            <tr>
              <th>Referral ID</th>
              <th>FIR No</th>
              <th>Reported</th>
              <th>Victim</th>
              <th style={{ textAlign: "right" }}>Amount (USDT)</th>
              <th>Suspect Wallet</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <Fragment key={r.id}>
                <tr>
                  <td><strong>{r.id}</strong></td>
                  <td className="mono" style={{ fontSize: 12 }}>{r.firNo}</td>
                  <td>{formatDate(r.reportedAt)}</td>
                  <td>{r.victimName}</td>
                  <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                    {r.amountUSDT.toLocaleString()}
                  </td>
                  <td className="mono" style={{ fontSize: 12 }}>
                    {r.suspectWallet.slice(0, 10)}…{r.suspectWallet.slice(-6)}
                  </td>
                  <td>
                    <Badge className={STATUS_BADGE[r.status]}>{STATUS_LABEL[r.status]}</Badge>
                    {r.triage ? (
                      <Badge className={RISK_BADGE[r.triage.risk]} style={{ marginLeft: 4 }}>
                        {r.triage.risk}
                      </Badge>
                    ) : null}
                  </td>
                  <td>
                    {r.status === "new" ? (
                      <Button size="sm" variant="primary" onClick={() => handleTriage(r.id)}>
                        Triage
                      </Button>
                    ) : r.status === "triaged" ? (
                      <Button size="sm" variant="primary" onClick={() => handleHandoff(r.id)}>
                        Hand Off
                      </Button>
                    ) : (
                      <span className="mono" style={{ fontSize: 12, color: "var(--green)" }}>
                        {r.handoffCaseId}
                      </span>
                    )}
                  </td>
                </tr>
                {expandedId === r.id && r.triage ? (
                  <tr key={`${r.id}-triage`} style={{ background: "var(--surface-2)" }}>
                    <td colSpan={8}>
                      <div style={{ padding: "var(--space-3) 0", display: "flex", gap: "var(--space-6)", flexWrap: "wrap", fontSize: "var(--text-sm)" }}>
                        <span><strong>Risk:</strong> <Badge className={RISK_BADGE[r.triage.risk]}>{r.triage.risk}</Badge></span>
                        <span><strong>Wallet age:</strong> {r.triage.walletAgeMonths} months</span>
                        <span><strong>Exchange exposed:</strong> {r.triage.exchangeExposed ? "Yes" : "No"}</span>
                        <span><strong>Prior flags:</strong> {r.triage.priorFlags}</span>
                        <span>
                          <strong>Recommendation:</strong>{" "}
                          <Badge className={r.triage.recommendation === "investigate" ? "status-escalated" : r.triage.recommendation === "monitor" ? "status-open" : "status-draft"}>
                            {r.triage.recommendation}
                          </Badge>
                        </span>
                        <span><strong>Triaged by:</strong> {r.triage.triagedBy}</span>
                      </div>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            ))}
            {!loading && filtered.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", color: "var(--text-faint)", padding: "var(--space-6)" }}>
                  No referrals match the current filters.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </Card>

      <Card title="How This Integrates" subtitle="In production, the I4C Sahyog API would push referrals here via a webhook or polling adapter.">
        <div style={{ fontSize: "var(--text-sm)", lineHeight: 1.7, color: "var(--text-muted)" }}>
          <p style={{ margin: "0 0 8px" }}>
            <strong>1. Complaint Intake:</strong> Victim files a cybercrime complaint through the NCRP portal.
            The complaint includes a suspect wallet address, transaction amounts, and FIR details.
          </p>
          <p style={{ margin: "0 0 8px" }}>
            <strong>2. Wallet Triage:</strong> CryptoTrace automatically assesses the suspect wallet — checking
            wallet age, exchange exposure, prior flags, and transaction patterns — and assigns a risk verdict
            and recommendation (investigate / monitor / watchlist).
          </p>
          <p style={{ margin: 0 }}>
            <strong>3. Investigation Handoff:</strong> Triage results are packaged into a CryptoTrace investigation
            case with evidence provenance, enabling the investigator to immediately begin graph tracing and
            VASP attribution.
          </p>
        </div>
      </Card>
    </div>
  );
}
