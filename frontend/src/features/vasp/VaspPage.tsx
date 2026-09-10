import { useSearchParams } from "react-router-dom";
import { PageHeader, Button, Card, DemoBadge, EmptyState, LoadingBlock, ConfidenceLevelBadge } from "@/components/ui";
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
  const { isDemo } = useDataSource();
  const { can } = useAuth();

  const { data: candidates, loading, error, reload } = useApi(() => attribution.candidates(wallet || undefined), [wallet]);
  const { data: provenance } = useApi(() => evidence.provenance(), [], { enabled: true });

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

  const ranked = candidates
    ? [...candidates].sort((a, b) => (CONF_RANK[a.confidenceLevel] ?? 3) - (CONF_RANK[b.confidenceLevel] ?? 3))
    : [];

  return (
    <div className="page">
      <PageHeader
        title="VASP Intelligence"
        subtitle="Candidate service-provider associations derived from wallet behavior. Results are candidates, not verified ownership."
        crumbs={[{ label: "VASP Intelligence" }]}
        actions={isDemo ? <DemoBadge label="SYNTHETIC ATTRIBUTION" /> : undefined}
      />

      <div className="risk-rule rr-high" role="note">
        <strong>Attribution caveat:</strong> confidence reflects available transactional and intelligence evidence. It is not proof of ownership.
      </div>

      {wallet ? (
        <Card title="Filtered by wallet" subtitle="Showing candidates for the selected wallet only.">
          <span className="mono" data-testid="vasp-wallet-filter">{wallet}</span>
        </Card>
      ) : null}

      {loading ? (
        <LoadingBlock />
      ) : error ? (
        <Card>
          <p style={{ color: "var(--text-muted)" }}>{error}</p>
          <Button onClick={reload}>Retry</Button>
        </Card>
      ) : !candidates?.length ? (
        <EmptyState
          title="No candidates"
          description={
            isDemo
              ? "The synthetic adapter returned no candidates for this wallet. Try removing the wallet filter."
              : "No attribution candidates were returned by the backend pipeline for this wallet."
          }
        />
      ) : (
        <div className="stack">
          {/* Ranking summary strip */}
          <Card title="Candidate ranking" subtitle="Sorted by confidence strength — strongest associations first.">
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
          {candidates.map((c) => (
            <CandidateCard key={c.id} candidate={c} />
          ))}
        </div>
      )}

      <Card title="Provenance chain" subtitle="How a candidate association is derived (synthetic today).">
        <ProvenanceChain links={provenance ?? []} />
      </Card>
    </div>
  );
}