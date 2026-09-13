import { useSearchParams } from "react-router-dom";
import { PageHeader, Button, Card, DemoBadge, Badge, EmptyState, LoadingBlock, ConfidenceLevelBadge } from "@/components/ui";
import { CandidateCard } from "@/components/attribution/CandidateCard";
import { useApi } from "@/hooks/useApi";
import { attribution } from "@/api/attribution";
import { evidence } from "@/api/evidence";
import { ProvenanceChain } from "@/components/evidence/EvidenceComponents";
import { useDataSource } from "@/app/DataSourceContext";
import { useAuth } from "@/auth/AuthContext";
import type { ConfidenceLevel } from "@/api/types";

const CONF_RANK: Record<ConfidenceLevel, number> = { high: 0, medium: 1, low: 2, unknown: 3 };

export function VaspPage() {
  const [params] = useSearchParams();
  const wallet = params.get("wallet") ?? "";
  const entity = params.get("entity") ?? "";
  const { isDemo } = useDataSource();
  const { can } = useAuth();

  const { data: candidates, loading, error, reload } = useApi(() => attribution.candidates(wallet || undefined), [wallet]);
  const { data: provenance } = useApi(() => evidence.provenance(), [], { enabled: true });
  const { data: directMatch } = useApi(() => (wallet ? attribution.intelligence(wallet) : Promise.resolve(null)), [wallet]);

  if (!can("attribution.read")) {
    return (
      <div className="page">
        <PageHeader title="VASP Intelligence" />
        <Card>
          <p style={{ color: "var(--text-muted)" }}>Your role does not permit viewing attribution intelligence.</p>
        </Card>
      </div>
    );
  }

  const ranked = (() => {
    if (!candidates) return [];
    const sorted = [...candidates].sort(
      (a, b) => (CONF_RANK[a.confidenceLevel] ?? 3) - (CONF_RANK[b.confidenceLevel] ?? 3),
    );
    if (!entity) return sorted;
    const q = entity.toLowerCase();
    return sorted.filter((c) => c.vaspName.toLowerCase().includes(q));
  })();

  return (
    <div className="page">
      <PageHeader
        title="VASP Intelligence"
        subtitle="Candidate service-provider associations derived from wallet behavior. Results are candidates, not verified ownership."
        crumbs={[{ label: "VASP Intelligence" }]}
        actions={isDemo ? <DemoBadge label="DEMO — SYNTHETIC EVIDENCE" /> : <Badge className="status-open">LIVE — REAL BLOCKCHAIN EVIDENCE</Badge>}
      />

      <div
        className="risk-rule rr-high"
        role="note"
        style={isDemo ? undefined : { background: "rgba(0,255,160,0.06)", borderLeftColor: "var(--success)" }}
      >
        <strong>{isDemo ? "DEMO mode" : "LIVE mode"}:</strong>{" "}
        {isDemo
          ? "Candidates are scored against the demo synthetic VASP directory. All evidence is labeled synthetic."
          : "Attribution is scored against the curated public VASP address directory. Evidence is derived from real blockchain data."}{" "}
        The score is an analytical ranking heuristic. It is NOT proof of wallet ownership or VASP association.
      </div>

      {wallet ? (
        <Card title="Filtered by wallet" subtitle="Showing candidates for the selected wallet only.">
          <span className="mono" data-testid="vasp-wallet-filter">{wallet}</span>
        </Card>
      ) : null}

      {entity ? (
        <Card title="Filtered by entity" subtitle={`Showing candidates matching "…${entity}…".`}>
          <span className="mono" data-testid="vasp-entity-filter">{entity}</span>
        </Card>
      ) : null}

      {wallet ? (
        <Card title="Direct known-address match" subtitle="Directory lookup of the queried wallet — a different question from behavioral candidates below.">
          {directMatch?.isKnownVasp ? (
            <div className="stack">
              <p className="status-open" style={{ margin: 0 }}>
                This wallet is listed directly in the curated VASP directory as{" "}
                <strong>{directMatch.knownVasp}</strong> ({directMatch.addressType ?? "address type unknown"}
                {directMatch.jurisdiction ? `, ${directMatch.jurisdiction}` : ""}) — {directMatch.matchCount} directory{" "}
                {directMatch.matchCount === 1 ? "match" : "matches"}.
              </p>
              <div className="detail-row">
                <span className="detail-label">Verification</span>
                <span className="detail-value">{directMatch.verificationStatus ?? "unverified"}</span>
              </div>
            </div>
          ) : (
            <p style={{ margin: 0 }}>
              None found — this wallet is not listed directly in the curated VASP directory. Any associations shown in{" "}
              <strong>Candidate ranking</strong> below are behavioral candidates derived from transaction history and graph
              proximity, not direct directory listings.
            </p>
          )}
        </Card>
      ) : null}

      {loading ? (
        <LoadingBlock />
      ) : error ? (
        <Card>
          <p style={{ color: "var(--text-muted)" }}>{error}</p>
          <Button onClick={reload}>Retry</Button>
        </Card>
      ) : !ranked.length ? (
        <EmptyState
          title="No candidates"
          description={
            isDemo
              ? "The synthetic adapter returned no candidates for this filter. Try removing the wallet/entity filter."
              : "No attribution candidates were returned by the backend pipeline for this filter."
          }
        />
      ) : (
        <div className="stack">
          {/* Ranking summary strip */}
          <Card
            title="Candidate ranking"
            subtitle="Behavioral/graph candidate associations — sorted by confidence strength. These are NOT direct directory matches."
          >
            <div className="rank-strip">
              {ranked.map((c, i) => (
                <div key={c.id} className={`rank-card ${i === 0 ? "rank-primary" : ""}`}>
                  <span className="rank-badge">{i + 1}</span>
                  <div className="rank-body">
                    <span className="rank-name">{c.vaspName}</span>
                    <span className="rank-meta">
                      <ConfidenceLevelBadge level={c.confidenceLevel} /> · {c.evidenceCount} evidence items · {c.confidenceScore !== null ? `${c.confidenceScore}%` : "score unavailable"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Detailed candidate cards */}
          {ranked.map((c) => (
            <CandidateCard key={c.id} candidate={c} />
          ))}
        </div>
      )}

      <Card
        title="Provenance chain"
        subtitle={
          isDemo
            ? "How a candidate association is derived in demo mode (synthetic dataset, clearly labeled)."
            : "How a candidate association is derived — scored against the curated public VASP directory."
        }
      >
        <ProvenanceChain links={provenance ?? []} />
      </Card>
    </div>
  );
}