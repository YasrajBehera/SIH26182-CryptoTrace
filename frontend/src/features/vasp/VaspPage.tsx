import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { PageHeader, Button, Card, DemoBadge, Badge, EmptyState, LoadingBlock, ConfidenceLevelBadge } from "@/components/ui";
import { CandidateCard } from "@/components/attribution/CandidateCard";
import { useApi } from "@/hooks/useApi";
import { attribution } from "@/api/attribution";
import { evidence } from "@/api/evidence";
import { investigations, mapPersistedCandidatesToView } from "@/api/investigations";
import { ProvenanceChain } from "@/components/evidence/EvidenceComponents";
import { useDataSource } from "@/app/DataSourceContext";
import { useAuth } from "@/auth/AuthContext";
import type { ConfidenceLevel } from "@/api/types";

const CONF_RANK: Record<ConfidenceLevel, number> = { high: 0, medium: 1, low: 2, unknown: 3 };

export function VaspPage() {
  const [params] = useSearchParams();
  const wallet = params.get("wallet") ?? "";
  const entity = params.get("entity") ?? "";
  const caseId = params.get("case") ?? "";
  const { isDemo } = useDataSource();
  const { can } = useAuth();

  // When a case is in scope the page shows ONLY the investigation's persisted
  // candidates (from the case context snapshot) — never a fresh pipeline run
  // and never a generic directory listing. Without a case it computes fresh
  // behavioral candidates for the queried wallet.
  const { data: context, loading: contextLoading, error: contextError, reload: reloadContext } = useApi(
    () => (caseId ? investigations.context(caseId) : Promise.resolve(null)),
    [caseId],
  );
  const { data: candidates, loading, error, reload } = useApi(
    () => (caseId ? Promise.resolve(null) : attribution.candidates(wallet || undefined)),
    [wallet, caseId],
  );
  const { data: provenance } = useApi(() => evidence.provenance(), [], { enabled: true });
  const { data: directMatch } = useApi(() => (wallet ? attribution.intelligence(wallet) : Promise.resolve(null)), [wallet]);

  // Effective candidate set: persisted case snapshot when investigation-scoped,
  // otherwise the freshly computed pipeline result.
  const sourceCandidates = useMemo(() => {
    if (caseId) return mapPersistedCandidatesToView(context ?? null);
    return candidates ?? [];
  }, [caseId, context, candidates]);

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

  const loadingState = caseId ? contextLoading : loading;
  const errorState = caseId ? contextError : error;
  const retry = caseId ? reloadContext : reload;

  const ranked = (() => {
    if (!sourceCandidates.length) return [];
    // The backend returns an explicit UNKNOWN placeholder when nothing scores.
    // Hide it from the ranking list (it is surfaced as a banner) so the UI
    // never implies a placement ranks a VASP that was not actually found.
    const known = sourceCandidates.filter((c) => c.vaspName.toLowerCase() !== "unknown");
    const sorted = [...known].sort(
      (a, b) => (CONF_RANK[a.confidenceLevel] ?? 3) - (CONF_RANK[b.confidenceLevel] ?? 3),
    );
    if (!entity) return sorted;
    const q = entity.toLowerCase();
    return sorted.filter((c) => c.vaspName.toLowerCase().includes(q));
  })();

  const hasUnknownPlaceholder = sourceCandidates.some((c) => c.vaspName.toLowerCase() === "unknown");
  const highestScore = ranked.reduce((max, c) => Math.max(max, c.confidenceScore ?? 0), 0);
  const noHighConfidence = !hasUnknownPlaceholder && wallet && ranked.length > 0 && highestScore < 70;

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
          : caseId
            ? "Showing the persisted attribution snapshot for the selected investigation — no fresh analysis is run from this page."
            : "Attribution is scored against the curated public VASP address directory. Evidence is derived from real blockchain data."}{" "}
        The score is an analytical ranking heuristic. It is NOT proof of wallet ownership or VASP association.
      </div>

      {caseId ? (
        <Card title="Investigation scope" subtitle="Candidates are the persisted analysis on this investigation — not a generic directory listing.">
          <span className="mono" data-testid="vasp-case-scope">{caseId}</span>
          {context?.case ? (
            <p style={{ margin: "8px 0 0", fontSize: "var(--text-sm)", color: "var(--text-faint)" }}>
              {context.case.name} · {context.case.risk ?? "Unknown"} risk ·{" "}
              {sourceCandidates.length} persisted {sourceCandidates.length === 1 ? "candidate" : "candidates"}
            </p>
          ) : null}
        </Card>
      ) : null}

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

      {!isDemo && wallet && hasUnknownPlaceholder ? (
        <Card title="No high-confidence VASP attribution found.">
          <p style={{ margin: 0 }} data-testid="vasp-high-confidence-none">
            This wallet was analyzed against the curated public VASP directory but no candidate reached a positive
            attribution score. No high-confidence VASP attribution found. There is currently no evidence that this wallet
            belongs to any service provider in the directory.
          </p>
        </Card>
      ) : null}

      {!isDemo && wallet && noHighConfidence ? (
        <Card title="No high-confidence VASP attribution found.">
          <p style={{ margin: 0 }} data-testid="vasp-high-confidence-none">
            The strongest candidate scores <strong>{highestScore}/100</strong>, below the HIGH confidence threshold
            (70). No high-confidence VASP attribution found. The candidates below remain behavioral associations only —
            they are NOT verified ownership.
          </p>
        </Card>
      ) : null}

      {loadingState ? (
        <LoadingBlock />
      ) : errorState ? (
        <Card>
          <p style={{ color: "var(--text-muted)" }}>{errorState}</p>
          <Button onClick={retry}>Retry</Button>
        </Card>
      ) : !ranked.length && !hasUnknownPlaceholder ? (
        <EmptyState
          title="No candidates"
          description={
            isDemo
              ? "The synthetic adapter returned no candidates for this filter. Try removing the wallet/entity filter."
              : "No attribution candidates were returned by the backend pipeline for this filter."
          }
        />
      ) : !ranked.length && hasUnknownPlaceholder ? (
        <EmptyState
          title="No attribution signal"
          description="The pipeline analyzed this wallet but every candidate scored zero. No high-confidence VASP attribution found."
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