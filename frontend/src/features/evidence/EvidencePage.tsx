import { useSearchParams } from "react-router-dom";
import { PageHeader, Button, Card, DemoBadge, Input, Field, Textarea, EmptyState, LoadingBlock, Badge } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { evidence } from "@/api/evidence";
import { EvidenceCard, ProvenanceChain } from "@/components/evidence/EvidenceComponents";
import { useDataSource } from "@/app/DataSourceContext";
import { useAuth } from "@/auth/AuthContext";
import { useToast } from "@/components/ui";
import { useEffect, useState } from "react";
import { validateAddressInput } from "@/lib/address";
import type { EvidenceItem } from "@/api/types";

export function EvidencePage() {
  const [params] = useSearchParams();
  const wallet = params.get("wallet") ?? "";
  const focus = params.get("focus") ?? "";
  const { isDemo } = useDataSource();
  const { can } = useAuth();
  const { push } = useToast();

  const [title, setTitle] = useState("");
  const [source, setSource] = useState("");
  const [relatedWallet, setRelatedWallet] = useState("");
  const [notes, setNotes] = useState("");

  const { data: items, loading, error, reload } = useApi(() => evidence.list(wallet || undefined), [wallet]);
  const { data: provenance } = useApi(() => evidence.provenance(), []);

  const walletProblem = relatedWallet ? validateAddressInput(relatedWallet) : null;

  useEffect(() => {
    if (!focus) return;
    const t = window.setTimeout(() => {
      document.getElementById(`evidence-${focus}`)?.scrollIntoView({ block: "center", behavior: "smooth" });
    }, 60);
    return () => window.clearTimeout(t);
  }, [focus, items]);

  const attach = (e: React.FormEvent) => {
    e.preventDefault();
    if (walletProblem) return;
    push({
      kind: "info",
      title: "Evidence attachment (demo)",
      description: "Persisting evidence requires the Member 3 evidence service. The item was not saved.",
    });
    setTitle("");
    setSource("");
    setRelatedWallet("");
    setNotes("");
  };

  const remove = async (item: EvidenceItem) => {
    if (!window.confirm(`Delete evidence ${item.id}? This action cannot be undone.`)) return;
    try {
      await evidence.delete(item.id);
      push({ kind: "ok", title: "Evidence deleted", description: `${item.id} was removed (demo — not persisted).` });
      reload();
    } catch (err) {
      push({ kind: "error", title: "Delete failed", description: err instanceof Error ? err.message : "Unknown error." });
    }
  };

  return (
    <div className="page">
      <PageHeader
        title="Evidence"
        subtitle="Collect, classify, and preserve evidence with provenance. Forwarding to checksummed store is pending."
        crumbs={[{ label: "Evidence" }]}
        actions={isDemo ? <DemoBadge label="SYNTHETIC EVIDENCE" /> : undefined}
      />

      {can("evidence.create") ? (
        <Card
          title="Attach evidence"
          subtitle="Record source material for a wallet or transaction. Only lawful, public information in this system."
        >
          <form className="stack" onSubmit={attach}>
            <div className="grid grid-2">
              <Field label="Title" htmlFor="ev-title">
                <Input id="ev-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Chain explorer transaction view" required />
              </Field>
              <Field label="Source" htmlFor="ev-source">
                <Input id="ev-source" value={source} onChange={(e) => setSource(e.target.value)} placeholder="e.g. Etherscan, court filing, report" />
              </Field>
            </div>
            <Field label="Related wallet (optional)" htmlFor="ev-wallet" error={walletProblem ?? undefined}>
              <Input id="ev-wallet" className="mono" value={relatedWallet} invalid={!!walletProblem} onChange={(e) => setRelatedWallet(e.target.value)} placeholder="0x…" />
            </Field>
            <Field label="Notes" htmlFor="ev-notes">
              <Textarea id="ev-notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="What does this evidence show?" />
            </Field>
            <div className="row">
              <Button variant="primary" type="submit" disabled={!title.trim() || !!walletProblem}>
                Attach evidence
              </Button>
              <Badge className="status-pending">Store pending</Badge>
            </div>
          </form>
        </Card>
      ) : null}

      {wallet ? (
        <Card title="Filtered by wallet">
          <span className="mono" data-testid="evidence-wallet-filter">{wallet}</span>
        </Card>
      ) : null}

      <Card
        title="Evidence items"
        subtitle={`${items?.length ?? 0} items`}
        actions={<Button variant="ghost" size="sm" onClick={reload}>↻ Refresh</Button>}
      >
        {items?.length ? (
          <div className="evidence-labels" aria-label="Evidence fields">
            <span>ID</span>
            <span>Type</span>
            <span>Source — provenance</span>
            <span>When</span>
            <span>Reliability</span>
            <span>Related wallet / tx</span>
          </div>
        ) : null}
        {loading ? (
          <LoadingBlock />
        ) : error ? (
          <div className="stack">
            <p style={{ color: "var(--text-muted)" }}>{error}</p>
            <Button onClick={reload}>Retry</Button>
          </div>
        ) : !items?.length ? (
          <EmptyState title="No evidence items" description={isDemo ? "Synthetic evidence is unavailable for this wallet." : "Evidence service (Member 3) is not connected."} />
        ) : (
          <div className="stack">
            {items.map((it) => (
              <EvidenceCard
                key={it.id}
                item={it}
                focused={focus === it.id}
                onDelete={can("evidence.delete") ? (item) => void remove(item) : undefined}
              />
            ))}
          </div>
        )}
      </Card>

      <Card title="Provenance chain">
        <ProvenanceChain links={provenance ?? []} />
      </Card>
    </div>
  );
}