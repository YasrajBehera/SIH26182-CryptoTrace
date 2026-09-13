import type { ReportConfig, ReportSectionKey } from "@/api/types";
import { Badge } from "@/components/ui";
import { formatDate } from "@/lib/format";
import type { Investigation, BlockchainTransfer, AttributionCandidate, EvidenceItem, InvestigationTimelineEvent } from "@/api/types";

export const REPORT_SECTION_LABELS: Record<ReportSectionKey, string> = {
  executive_summary: "Executive Summary",
  investigation_details: "Investigation Details",
  wallet_overview: "Wallet Overview",
  transaction_analysis: "Transaction Analysis",
  fund_flow: "Fund Flow",
  graph_analysis: "Graph Analysis",
  vasp_candidates: "VASP Candidates",
  evidence: "Evidence",
  risk_assessment: "Risk Assessment",
  analyst_notes: "Analyst Notes",
  timeline: "Timeline",
  conclusion: "Conclusion",
  appendix: "Appendix",
};

export const ALL_REPORT_SECTIONS = Object.keys(REPORT_SECTION_LABELS) as ReportSectionKey[];

/* ---- Section toggles ---- */

export function ReportSectionSelector({
  sections,
  onToggle,
}: {
  sections: ReportSectionKey[];
  onToggle: (key: ReportSectionKey) => void;
}) {
  return (
    <div
      className="grid"
      style={{ gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))", gap: 8 }}
      role="group"
      aria-label="Report sections"
    >
      {ALL_REPORT_SECTIONS.map((key) => {
        const active = sections.includes(key);
        return (
          <label key={key} className={`section-toggle ${active ? "" : "off"}`}>
            <span style={{ fontSize: "var(--text-sm)", fontWeight: 550 }}>{REPORT_SECTION_LABELS[key]}</span>
            <input
              type="checkbox"
              className="sr-only"
              checked={active}
              onChange={() => onToggle(key)}
              aria-label={`Include ${REPORT_SECTION_LABELS[key]}`}
            />
            <span className={`switch ${active ? "on" : ""}`} aria-hidden />
          </label>
        );
      })}
    </div>
  );
}

/* ---- Report preview document ---- */

interface ReportData {
  investigation: Investigation | null;
  transfers: BlockchainTransfer[];
  candidates: AttributionCandidate[];
  evidence: EvidenceItem[];
  timeline: InvestigationTimelineEvent[];
}

export function ReportPreview({
  config,
  data,
  mode,
}: {
  config: ReportConfig;
  data: ReportData;
  mode: "live" | "demo";
}) {
  const { metadata, sections } = config;
  const has = (k: ReportSectionKey) => sections.includes(k);

  return (
    <div className="report-doc" data-testid="report-preview" id="report-preview">
      <section className="report-title-page">
        <div className="report-classification">{metadata.classification}</div>
        <h1 style={{ marginTop: "var(--space-4)", fontSize: 28 }}>Investigation Report</h1>
        <p style={{ color: "var(--text-muted)" }}>CryptoTrace — Blockchain Investigation Platform</p>
        <p style={{ color: "var(--text-faint)", fontSize: "var(--text-sm)" }}>
          Case {metadata.caseId} · Generated {formatDate(metadata.generatedAt)} · Investigator {metadata.investigator}
        </p>
        <p style={{ color: "var(--text-faint)", fontSize: "var(--text-sm)" }}>
          Data source: {mode === "demo" ? "DEMO — synthetic evidence" : `LIVE — ${metadata.network} (blockchain evidence)`}
        </p>
      </section>

      {mode === "demo" ? (
        <div style={{ textAlign: "center" }}>
          <Badge className="badge-demo">DEMO/MOCK REPORT — preview of generated output only</Badge>
        </div>
      ) : null}

      {has("executive_summary") ? (
        <section className="report-section">
          <h2>Executive Summary</h2>
          <p>
            This report documents an investigative review of wallet{" "}
            <strong>{metadata.primaryWallet}</strong> on {metadata.network}. It describes transaction flows,
            candidate service-provider associations, and the available evidence. All attribution statements are
            candidate-level; none are claims of verified ownership unless independently established.
          </p>
          {data.investigation ? <p>{data.investigation.description}</p> : null}
        </section>
      ) : null}

      {has("investigation_details") ? (
        <section className="report-section">
          <h2>Investigation Details</h2>
          <ReportTable
            rows={[
              ["Case ID", metadata.caseId ?? "—"],
              ["Case name", data.investigation?.name ?? "—"],
              ["Investigator", metadata.investigator],
              ["Generated", formatDate(metadata.generatedAt)],
              ["Network", metadata.network],
              ["Primary wallet", metadata.primaryWallet],
              ["Status", data.investigation?.status ?? "—"],
              ["Assigned analyst", data.investigation?.assignedAnalyst ?? "—"],
            ]}
          />
        </section>
      ) : null}

      {has("wallet_overview") ? (
        <section className="report-section">
          <h2>Wallet Overview</h2>
          <ReportTable
            rows={[
              ["Wallet address", metadata.primaryWallet],
              ["Network", metadata.network],
              ["Transactions traced", String(data.transfers.length)],
              ["Risk level", data.investigation?.risk ?? "unknown"],
              ["Tags", data.investigation?.tags.join(", ") ?? "—"],
            ]}
          />
        </section>
      ) : null}

      {has("transaction_analysis") ? (
        <section className="report-section">
          <h2>Transaction Analysis</h2>
          <p>Representative normalized transfers from the dataset:</p>
          <table className="report-table">
            <thead>
              <tr>
                <th>Hash</th>
                <th>Direction</th>
                <th>From</th>
                <th>To</th>
                <th>Asset</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {data.transfers.slice(0, 12).map((t, i) => (
                <tr key={`${t.transaction_hash}-${i}`}>
                  <td className="mono" style={{ fontSize: 11 }}>{t.transaction_hash.slice(0, 14)}…</td>
                  <td>{t.direction}</td>
                  <td className="mono" style={{ fontSize: 11 }}>{t.from_address.slice(0, 10)}…</td>
                  <td className="mono" style={{ fontSize: 11 }}>{t.to_address.slice(0, 10)}…</td>
                  <td>{t.asset}</td>
                  <td className="mono">{Number(t.value).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}

      {has("fund_flow") ? (
        <section className="report-section">
          <h2>Fund Flow</h2>
          <p>
            Fund-flow reconstruction is served by the graph engine when a temporal path is available for the subject
            wallet. When no graph path exists for this case, this section reports UNAVAILABLE rather than inventing a
            flow.
          </p>
        </section>
      ) : null}

      {has("graph_analysis") ? (
        <section className="report-section">
          <h2>Graph Analysis</h2>
          <p>
            Graph analytics (neighbors, paths, temporal fund flow) are computed by the Neo4j-backed graph engine for
            investigated wallets. Graph data source status is reported by the live system status endpoint; no synthetic
            topology is presented in live mode.
          </p>
        </section>
      ) : null}

      {has("vasp_candidates") ? (
        <section className="report-section">
          <h2>VASP Candidates</h2>
          {data.candidates.length ? (
            <table className="report-table">
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th>Confidence</th>
                  <th>State</th>
                  <th>Evidence</th>
                </tr>
              </thead>
              <tbody>
                {data.candidates.map((c) => (
                  <tr key={c.id}>
                    <td>{c.vaspName}</td>
                    <td>{c.confidenceLevel}</td>
                    <td>{c.state}</td>
                    <td>{c.evidenceCount}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p>No candidates recorded for this case.</p>
          )}
          <p style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)" }}>
            All candidates are potential associations; verified ownership requires independent backend evidence.
          </p>
        </section>
      ) : null}

      {has("evidence") ? (
        <section className="report-section">
          <h2>Evidence</h2>
          {data.evidence.length ? (
            <ReportTable
              rows={data.evidence.map((e) => [e.id, e.title, e.type, e.reliability, e.checksum ?? "—"] as [string, string, string, string, string])}
            />
          ) : (
            <p>No evidence items attached.</p>
          )}
        </section>
      ) : null}

      {has("risk_assessment") ? (
        <section className="report-section">
          <h2>Risk Assessment</h2>
          <p>
            Overall risk for this case is assessed at <strong>{data.investigation?.risk ?? "unknown"}</strong>.
            Risk scoring is currently derived from investigation-level flags. A dedicated risk engine is not
            connected yet.
          </p>
        </section>
      ) : null}

      {has("analyst_notes") ? (
        <section className="report-section">
          <h2>Analyst Notes</h2>
          <p>The analyst notes section is reserved for investigator narrative. It is not populated in this demo.</p>
        </section>
      ) : null}

      {has("timeline") ? (
        <section className="report-section">
          <h2>Timeline</h2>
          {data.timeline.length ? (
            <ReportTable rows={data.timeline.map((t) => [formatDate(t.at), t.actor, t.action, t.category ?? ""] as [string, string, string, string])} />
          ) : (
            <p>No timeline events.</p>
          )}
        </section>
      ) : null}

      {has("conclusion") ? (
        <section className="report-section">
          <h2>Conclusion</h2>
          <p>
            This report summarizes available intelligence. No conclusion of ownership or wrongdoing is implied
            where evidence is insufficient. Further analysis is required before any law-enforcement or compliance
            decision is made.
          </p>
        </section>
      ) : null}

      {has("appendix") ? (
        <section className="report-section">
          <h2>Appendix</h2>
          <p>Appendix materials (raw data dumps, explorer links, methodology) belong here in a full export.</p>
        </section>
      ) : null}

      <footer className="report-footer-note">
        Generated by CryptoTrace. {mode === "demo" ? "This document is a synthetic preview. " : ""}No blockchain
        data in previews is presented as authoritative; verify on-chain before use.
      </footer>
    </div>
  );
}

export function ReportTable({ rows }: { rows: Array<[string, string]> | Array<[string, string, string, string]> | Array<[string, string, string, string, string]> }) {
  const cols = rows[0]?.length ?? 2;
  return (
    <table className="report-table">
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            {Array.from({ length: cols }, (_, c) => (
              <td key={c} style={{ fontWeight: c === 0 ? 600 : 400 }}>
                {(r as string[])[c]}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}