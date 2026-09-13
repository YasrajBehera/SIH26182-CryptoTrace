import { useState } from "react";
import { Button, Card, Badge, DemoBadge, Textarea, InlineSpinner, ConfirmDialog } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { assistant } from "@/api/assistant";
import type { AssistantDataSource, AssistantResponse, AssistantQuickAction, ReferralDraft } from "@/api/types";

interface InvestigatorAssistantProps {
  caseId?: string;
  walletAddress?: string;
  chain?: string;
  /** Scope filters the quick actions offered (case vs wallet). */
  scope?: "case" | "wallet";
  compact?: boolean;
}

const SOURCE_LABEL: Record<AssistantDataSource, string> = {
  live: "LIVE DATA",
  demo: "DEMO",
  mixed: "MIXED",
  unavailable: "UNAVAILABLE",
};

function sourceClass(source: AssistantDataSource): string {
  if (source === "live") return "status-success";
  if (source === "demo") return "badge-demo";
  if (source === "mixed") return "status-warning";
  return "status-draft";
}

function ReferralPanel({ draft, demo }: { draft: ReferralDraft; demo: boolean }) {
  return (
    <div className="card" style={{ marginTop: 12, borderColor: "var(--color-border-strong)" }} data-testid="assistant-referral">
      <div className="card-header">
        <div>
          <h4 className="card-title">{draft.title}</h4>
          <p className="card-sub">
            {draft.submission_state.replace(/_/g, " ")} · SAHYOG {draft.sahyog_status}
          </p>
        </div>
        <div className="row">
          {demo ? <DemoBadge label="DRAFT" /> : null}
          <Badge className="status-draft">never submitted autonomously</Badge>
        </div>
      </div>
      <div className="card-body">
        <p style={{ margin: 0, color: "var(--text-muted)" }}>{draft.summary}</p>
        <dl className="detail-grid" style={{ marginTop: 8 }}>
          <div className="detail-row">
            <dt className="detail-label">Case</dt>
            <dd className="detail-value">{draft.case_id}</dd>
          </div>
          <div className="detail-row">
            <dt className="detail-label">Wallet</dt>
            <dd className="detail-value mono">{draft.primary_wallet}</dd>
          </div>
          <div className="detail-row">
            <dt className="detail-label">Risk</dt>
            <dd className="detail-value">{draft.risk_level}{draft.risk_score != null ? ` (${draft.risk_score})` : ""}</dd>
          </div>
          <div className="detail-row">
            <dt className="detail-label">Evidence</dt>
            <dd className="detail-value">{draft.evidence_ids.length} records · {draft.transaction_hashes.length} transactions</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}

function ResponseBody({ response }: { response: AssistantResponse }) {
  const demo = response.data_source === "demo";
  return (
    <div className="stack" data-testid="assistant-response">
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        {demo ? <DemoBadge /> : null}
        <Badge className={sourceClass(response.data_source)}>{SOURCE_LABEL[response.data_source]}</Badge>
        {response.human_review_required ? <Badge className="status-review">human review required</Badge> : null}
        {response.request_id ? <span className="mono" style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)" }}>{response.request_id}</span> : null}
      </div>

      {response.warnings.length ? (
        <ul style={{ margin: 0, paddingLeft: 0, listStyle: "none" }}>
          {response.warnings.map((w, i) => (
            <li key={i}>
              <Badge className="status-warning" style={{ marginBottom: 4 }}>⚠ {w}</Badge>
            </li>
          ))}
        </ul>
      ) : null}

      {response.sections.map((section, i) => (
        <section key={`${i}-${section.heading}`}>
          <h4 className="card-title" style={{ marginBottom: 4 }}>{section.heading}</h4>
          {section.body ? <p style={{ margin: "0 0 6px", color: "var(--text-muted)" }}>{section.body}</p> : null}
          {section.bullets.length ? (
            <ul style={{ margin: "6px 0", listStyle: "disc", paddingInlineStart: 18 }}>
              {section.bullets.map((b, j) => (
                <li key={j} style={{ marginBottom: 2 }}>
                  {b}
                </li>
              ))}
            </ul>
          ) : null}
          {section.actions.length ? (
            <ul style={{ margin: "6px 0", listStyle: "none", paddingInlineStart: 0 }}>
              {section.actions.map((a, j) => (
                <li key={j} className="mono" style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)" }}>
                  → {a}
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ))}

      {response.referral_draft ? <ReferralPanel draft={response.referral_draft} demo={demo} /> : null}

      <p className="text-dim" style={{ margin: 0, fontSize: "var(--text-xs)" }}>
        {response.disclaimer}
      </p>
    </div>
  );
}

/**
 * M9 Investigator Assistant.
 *
 * An evidence-grounded advisor surface: it answers questions from persisted
 * case/wallet/evidence/risk facts. It never invents data — when a fact is
 * absent the answer says so — and it never submits referrals or discharges any
 * operational action; every response requires human review.
 */
export function InvestigatorAssistant({ caseId, walletAddress, chain = "eth", scope = "case", compact }: InvestigatorAssistantProps) {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<AssistantResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [askedForIntent, setAskedForIntent] = useState<string | undefined>(undefined);
  const [pendingAction, setPendingAction] = useState<AssistantQuickAction | null>(null);

  const { data: actions, loading: actionsLoading, reload: reloadActions } = useApi<AssistantQuickAction[]>(() => assistant.quickActions(), []);
  const actionsForScope = actions?.filter((a) => a.scope === scope) ?? [];
  const fallbackActions = actions?.length ? actionsForScope : undefined;

  const ask = async (intent?: string, text?: string) => {
    const payloadText = (text ?? query).trim();
    if (!payloadText) return;
    setRunning(true);
    setError(null);
    setAskedForIntent(intent);
    try {
      const res = await assistant.query({
        query: payloadText,
        intent,
        caseId,
        walletAddress,
        chain,
      });
      setResponse(res);
    } catch (err) {
      const message = err instanceof Error ? err.message : "The assistant could not be reached.";
      setError(message);
      setResponse(null);
    } finally {
      setRunning(false);
    }
  };

  const runQuickAction = (action: AssistantQuickAction) => {
    if (action.requires_confirmation) {
      setPendingAction(action);
      return;
    }
    setQuery(action.label);
    void ask(action.id, action.label);
  };

  const confirmPendingAction = () => {
    const action = pendingAction;
    setPendingAction(null);
    if (action) {
      setQuery(action.label);
      void ask(action.id, action.label);
    }
  };

  return (
    <Card
      title="Investigator assistant"
      subtitle="Evidence-grounded answers from persisted cases, wallets, transactions and evidence. Never runs analysis, never acts on its own."
      actions={
        actionsLoading ? (
          <InlineSpinner />
        ) : (
          <Button variant="ghost" size="sm" onClick={reloadActions}>↻ Refresh intents</Button>
        )
      }
    >
      <div className="stack">
        {fallbackActions && fallbackActions.length ? (
          <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
            {fallbackActions.map((a) => (
              <Button key={a.id} variant="ghost" size="sm" disabled={running} onClick={() => runQuickAction(a)} title={a.description}>
                {a.label}
              </Button>
            ))}
          </div>
        ) : null}

        <form
          className="row"
          style={{ gap: 8, alignItems: "flex-start" }}
          onSubmit={(e) => {
            e.preventDefault();
            void ask();
          }}
        >
          <Textarea
            rows={compact ? 2 : 3}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={`Ask anything about ${caseId ? `case ${caseId}` : walletAddress ? "this wallet" : "a case or wallet"} — e.g. “summarize the case”, “trace funds”, “is anything suspicious?”`}
            aria-label="Assistant question"
            disabled={running}
          />
          <Button variant="primary" type="submit" disabled={running || !query.trim()}>
            {running ? <InlineSpinner /> : "Ask"}
          </Button>
        </form>

        {error ? (
          <p role="alert" className="text-dim" style={{ margin: 0, color: "var(--red)" }}>
            {error}
          </p>
        ) : null}

        {running ? (
          <div className="state" role="status">
            <span className="inline-spinner" aria-hidden />
            <p className="state-desc">{askedForIntent ? "Assembling a grounded answer…" : "Answering…"}</p>
          </div>
        ) : response ? (
          <ResponseBody response={response} />
        ) : null}

        {!running && !response && !error ? (
          <p className="text-dim" style={{ margin: "4px 0 0", fontSize: "var(--text-xs)" }}>
            Pick a quick action or type a question. Answers reflect only persisted, authorized data; unavailable facts are reported, never invented.
          </p>
        ) : null}
      </div>

      <ConfirmDialog
        open={pendingAction !== null}
        title={`Review before executing: ${pendingAction?.label ?? ""}`}
        description="This action assembles a DRAFT for your review. CryptoTrace never submits referrals or discharges enforcement action autonomously — you must review and finalize it yourself, outside the platform."
        confirmLabel="Draft for review"
        cancelLabel="Cancel"
        onConfirm={confirmPendingAction}
        onCancel={() => setPendingAction(null)}
      />
    </Card>
  );
}