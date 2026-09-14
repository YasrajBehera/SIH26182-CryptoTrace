import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { PageHeader, Card, DemoBadge, Badge, Select, Field, Input, LoadingBlock } from "@/components/ui";
import { InvestigatorAssistant } from "./InvestigatorAssistant";
import { useApi } from "@/hooks/useApi";
import { investigations } from "@/api/investigations";
import { useDataSource } from "@/app/DataSourceContext";
import { useAuth } from "@/auth/AuthContext";
import { validateAddressInput } from "@/lib/address";
import type { Investigation } from "@/api/types";

/**
 * Standalone Investigator Assistant page (/assistant).
 *
 * The assistant is evidence-grounded: it answers only from persisted,
 * authorized case/wallet/evidence/risk data and never invents facts or acts
 * autonomously (see InvestigatorAssistant).
 */
export function AssistantPage() {
  const [params, setParams] = useSearchParams();
  const { isDemo } = useDataSource();
  const { can } = useAuth();

  const caseParam = params.get("case") ?? "";
  const walletParam = params.get("wallet") ?? "";

  const { data: cases, loading: casesLoading } = useApi<Investigation[]>(() => investigations.list(), []);
  const [selectedCase, setSelectedCase] = useState(caseParam);
  const [walletInput, setWalletInput] = useState(walletParam);
  const walletValid = walletInput && validateAddressInput(walletInput) === null;

  const activeCase = cases?.find((c) => c.id === selectedCase) ?? null;
  const walletAddress = activeCase?.primaryWallet ?? (walletValid ? walletInput : "");

  if (!can("investigation.read")) {
    return (
      <div className="page">
        <PageHeader title="Investigator Assistant" />
        <Card>
          <p style={{ color: "var(--text-muted)" }}>Your role does not permit using the assistant.</p>
        </Card>
      </div>
    );
  }

  const setSearch = (next: { caseKey?: string; walletKey?: string }) => {
    const value: Record<string, string> = {};
    if (next.caseKey) value.case = next.caseKey;
    if (next.walletKey) value.wallet = next.walletKey;
    setParams(value);
  };

  return (
    <div className="page">
      <PageHeader
        title="Investigator Assistant"
        subtitle="Evidence-grounded Q&A over persisted investigations, wallets, transactions and evidence. Answers are grounded in the data the system actually holds."
        crumbs={[{ label: "Investigator Assistant" }]}
        actions={isDemo ? <DemoBadge label="DEMO — SYNTHETIC FACTS" /> : <Badge className="status-open">LIVE — PERSISTED FACTS</Badge>}
      />

      <Card title="Context" subtitle="Choose what the assistant answers about. A linked case scopes grounding to that investigation.">
        {casesLoading && !cases ? (
          <LoadingBlock label="Loading investigations…" />
        ) : (
          <div className="grid" style={{ gridTemplateColumns: "minmax(0, 1.4fr) minmax(0, 1fr)", gap: 12, alignItems: "end" }}>
            <Field label="Case" hint="Optional — grounds answers in the selected investigation.">
              <Select
                value={selectedCase}
                placeholder="No case — scope by wallet below"
                onChange={(e) => {
                  const next = e.target.value;
                  setSelectedCase(next);
                  if (next) setSearch({ caseKey: next });
                }}
                aria-label="Select case"
              >
                <option value="">No case — scope by wallet below</option>
                {(cases ?? []).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.id} — {c.name} · {c.primaryWallet}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Primary wallet" hint={activeCase ? "Pre-filled from the selected case." : "Optional — scope by wallet when no case is selected."}>
              <Input
                className="mono"
                value={walletInput}
                invalid={!!walletInput && !walletValid}
                onChange={(e) => {
                  const next = e.target.value;
                  setWalletInput(next);
                  if (validateAddressInput(next) === null) setSearch({ walletKey: next });
                }}
                placeholder="0x…"
                aria-label="Wallet address"
              />
            </Field>
          </div>
        )}
      </Card>

      {!activeCase && !walletAddress ? (
        <Card>
          <p style={{ margin: 0, color: "var(--text-muted)" }}>
            Select a case or enter a wallet address above to begin. Without context the assistant can only speak about
            which investigations exist.
          </p>
        </Card>
      ) : (
        <InvestigatorAssistant
          caseId={activeCase?.id}
          walletAddress={walletAddress}
          chain="eth"
          scope={activeCase ? "case" : "wallet"}
        />
      )}

      <Card title="How grounding works" subtitle="What the assistant can and cannot do.">
        <ul style={{ margin: 0, paddingInlineStart: 18, lineHeight: 1.7, color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
          <li>Answers are assembled from persisted, authorized facts (case record, wallet summary, transfers, evidence, risk, generated reports).</li>
          <li>Missing facts are reported as unavailable — the assistant never invents data.</li>
          <li>It never runs an analysis pipeline, never submits referrals, and never discharges any operational action autonomously.</li>
          <li>Every suggested action produces a draft requiring human review.</li>
        </ul>
      </Card>
    </div>
  );
}