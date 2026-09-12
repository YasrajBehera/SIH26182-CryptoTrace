import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { investigations } from "@/api/investigations";
import { CandidateCard } from "@/components/attribution/CandidateCard";
import { EvidenceCard, ProvenanceChain } from "@/components/evidence/EvidenceComponents";
import { GraphIcon, TraceIcon, TxIcon, EvidenceIcon } from "@/components/icons";
import {
  Badge,
  Button,
  Card,
  ConfidenceLevelBadge,
  DemoBadge,
  ErrorState,
  Field,
  Input,
  LoadingBlock,
  MetricCard,
  useToast,
} from "@/components/ui";
import { containsSecretMaterial, validateAddressInput } from "@/lib/address";
import { chainLabel, shortenAddress } from "@/lib/format";
import type { InvestigationAnalysis, ProvenanceLink } from "@/api/types";

function humanize(value?: string | null): string {
  if (!value) return "—";
  return value.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase());
}

/**
 * Standalone end-to-end analyzer for the live backend pipeline:
 * POST /api/v1/investigations/{address}/analyze  -> graph + attribution,
 * GET  /api/v1/evidence/attribution/{analysis_id} -> evidence/provenance.
 *
 * Never claims ownership: every result surfaces the backend disclaimer and
 * labels synthetic transaction data honestly.
 */
export function InvestigationAnalyzer() {
  const navigate = useNavigate();
  const { push } = useToast();
  const [params, setParams] = useSearchParams();
  const urlAddress = params.get("address") ?? "";
  const caseId = params.get("case") ?? "";

  const [address, setAddress] = useState(urlAddress);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<InvestigationAnalysis | null>(null);

  useEffect(() => {
    if (urlAddress && urlAddress !== address) setAddress(urlAddress);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlAddress]);

  const addressProblem = address ? validateAddressInput(address) : null;
  const canRun = !running && !!address && !addressProblem;

  const doAnalyze = async (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) {
      setError("Enter a public wallet address to analyze.");
      return;
    }
    if (containsSecretMaterial(trimmed)) {
      setError("Private keys and seed phrases are never accepted. Only public addresses.");
      return;
    }
    const problem = validateAddressInput(trimmed);
    if (problem) {
      setError(problem);
      return;
    }

    setError(null);
    setRunning(true);
    setResult(null);
    try {
      const analysis = await investigations.analyze(trimmed, "eth", caseId || undefined);
      setResult(analysis);
      setParams({ address: trimmed, ...(caseId ? { case: caseId } : {}) }, { replace: true });
      push({
        kind: "ok",
        title: "Investigation complete",
        description: `${analysis.candidates.length} candidate(s) · ${analysis.evidence.length} evidence record(s) returned by the backend.`,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "The analysis service could not be reached.");
    } finally {
      setRunning(false);
    }
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (canRun) void doAnalyze(address);
  };

  const ranked = useMemo(() => {
    const list = result?.candidates ?? [];
    return [...list].sort((a, b) => (b.confidenceScore ?? 0) - (a.confidenceScore ?? 0));
  }, [result]);

  const provenance = useMemo<ProvenanceLink[]>(() => {
    if (!result) return [];
    const links: ProvenanceLink[] = [];
    ranked.slice(0, 3).forEach((c) => {
      links.push({
        id: `prov-cand-${c.id}`,
        label: `Candidate: ${c.vaspName}`,
        sublabel:
          c.confidenceScore !== null && c.confidenceScore !== undefined
            ? `${c.confidenceScore}% · ${c.confidenceLevel.toUpperCase()}`
            : c.confidenceLevel.toUpperCase(),
        kind: "candidate",
      });
    });
    result.evidence.slice(0, 8).forEach((e) => {
      links.push({
        id: `prov-ev-${e.id}`,
        label: `${e.id} — ${e.type.replace(/_/g, " ")}`,
        sublabel: e.source,
        kind: "evidence",
      });
    });
    links.push({
      id: "prov-source",
      label: "Attribution engine v0.1.0",
      sublabel: "synthetic transaction pipeline",
      kind: "source",
    });
    return links;
  }, [result, ranked]);

  return (
    <div className="stack">
      <form className="stack" data-testid="investigation-analyzer" onSubmit={submit}>
        <div className="input-group">
          <Field
            label="Wallet address (0x…)"
            htmlFor="analysis-address"
            error={addressProblem ?? undefined}
          >
            <Input
              id="analysis-address"
              className="mono"
              placeholder="0x… public wallet address"
              value={address}
              invalid={!!addressProblem}
              onChange={(e) => {
                setAddress(e.target.value);
                setError(null);
              }}
              aria-label="Wallet address to analyze"
              data-testid="analyze-address"
            />
          </Field>
          <Button
            variant="primary"
            type="submit"
            disabled={!canRun}
            leading={running ? <span className="inline-spinner" aria-hidden /> : <TraceIcon />}
          >
            {running ? "Analyzing…" : "Analyze"}
          </Button>
        </div>
        <p className="card-sub" style={{ margin: 0 }}>
          Runs the backend pipeline over synthetic transactions (Ethereum): graph → VASP attribution → evidence.
        </p>
      </form>

      {running ? <LoadingBlock label="Running the investigation pipeline…" /> : null}

      {error && !running ? (
        <ErrorState
          title="Investigation could not be completed"
          description={error}
          action={<Button variant="primary" onClick={() => void doAnalyze(address)}>Retry</Button>}
        />
      ) : null}

      {result && !running ? (
        <div className="stack" data-testid="analyze-result">
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            {result.isDemo ? (
              <DemoBadge label="DEMO RESULT — backend unreachable" />
            ) : result.syntheticTransactions ? (
              <DemoBadge label="SYNTHETIC TRANSACTIONS — backend pipeline" />
            ) : null}
            <Badge className="status-open">
              Analysis: {result.analysisId ?? "demo"}
            </Badge>
          </div>

          <div className="risk-rule rr-high" role="note">
            <strong>Attribution caveat:</strong> {result.disclaimer}
          </div>

          <div className="kpi-grid">
            <MetricCard label="Transfers ingested" value={result.transfersIngested} desc={result.isDemo ? "DEMO — synthetic adapter" : "Backend pipeline output"} />
            <MetricCard label="Graph nodes" value={result.graphNodes} desc="Backend graph summary" />
            <MetricCard label="Graph edges" value={result.graphEdges} desc="Backend graph summary" />
            <MetricCard label="Evidence records" value={result.evidenceCount} desc="Incl. provenance from the evidence service" />
          </div>

          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <Button leading={<GraphIcon />} onClick={() => navigate(`/graph?address=${encodeURIComponent(result.address)}`)}>
              Open in graph / fund flow
            </Button>
            <Button leading={<TxIcon />} onClick={() => navigate(`/transactions?wallet=${encodeURIComponent(result.address)}`)}>
              Transaction history
            </Button>
            <Button leading={<EvidenceIcon />} onClick={() => navigate(result.analysisId ? `/evidence?analysis_id=${encodeURIComponent(result.analysisId)}` : `/evidence?wallet=${encodeURIComponent(result.address)}`)}>
              Evidence workspace
            </Button>
          </div>

          <Card
            title="Wallet intelligence"
            subtitle={
              result.intelligence
                ? `Matches: ${result.intelligence.matchCount}`
                : "Known-address intelligence"
            }
          >
            {result.intelligence ? (
              <div className="detail-grid">
                <div className="stack">
                  <div className="detail-row">
                    <span className="detail-label">Known VASP</span>
                    <span className="detail-value">{humanize(result.intelligence.knownVasp)}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Address type</span>
                    <span className="detail-value">{humanize(result.intelligence.addressType)}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Entity type</span>
                    <span className="detail-value">{humanize(result.intelligence.entityType)}</span>
                  </div>
                </div>
                <div className="stack">
                  <div className="detail-row">
                    <span className="detail-label">Jurisdiction</span>
                    <span className="detail-value">{humanize(result.intelligence.jurisdiction)}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Verification</span>
                    <span className="detail-value">{humanize(result.intelligence.verificationStatus)}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Confidence / source</span>
                    <span className="detail-value">
                      {result.intelligence.confidence ? `${Math.round(result.intelligence.confidence * 100)}%` : "—"} ·{" "}
                      {humanize(result.intelligence.source)}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
                No known-address intelligence for this wallet in the current (synthetic) dataset.
              </p>
            )}
          </Card>

          <Card
            title="Ranked VASP candidates"
            subtitle="Sorted by attribution score — strongest association first. Candidates, not verified ownership."
          >
            {ranked.length ? (
              <div className="stack">
                <div className="rank-strip">
                  {ranked.map((c, i) => (
                    <div key={c.id} className={`rank-card ${i === 0 ? "rank-primary" : ""}`}>
                      <span className="rank-badge">{i + 1}</span>
                      <div className="rank-body">
                        <span className="rank-name">{c.vaspName}</span>
                        <span className="rank-meta">
                          <ConfidenceLevelBadge level={c.confidenceLevel} /> · {c.evidenceCount} evidence items ·{" "}
                          {c.confidenceScore !== null && c.confidenceScore !== undefined
                            ? `${c.confidenceScore}%`
                            : "score unavailable"}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
                {ranked.map((c) => (
                  <CandidateCard key={c.id} candidate={c} />
                ))}
              </div>
            ) : (
              <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
                The backend returned no attribution candidates for this address.
              </p>
            )}
          </Card>

          <Card
            title="Evidence / provenance"
            subtitle={`${result.evidence.length} evidence record(s) returned by the backend evidence service`}
          >
            {result.evidence.length ? (
              <div className="stack">
                {result.evidence.map((item) => (
                  <EvidenceCard key={item.id} item={item} />
                ))}
              </div>
            ) : (
              <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
                No evidence records were returned for this analysis.
              </p>
            )}

            <div style={{ marginTop: 12 }}>
              <ProvenanceChain links={provenance} />
            </div>
            <p className="card-sub" style={{ margin: "12px 0 0" }}>
              Wallet <span className="mono">{shortenAddress(result.address, 10, 8)}</span> on {chainLabel(result.chain)}.
            </p>
          </Card>
        </div>
      ) : null}
    </div>
  );
}