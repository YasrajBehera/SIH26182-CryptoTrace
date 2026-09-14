import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageHeader, Button, Card, Badge, DemoBadge, RiskBadge, StatusBadge, ShortAddress, SkeletonBlock, EmptyState, ErrorState, SimpleTimeline, Textarea, Field, Tabs } from "@/components/ui";
import { TraceIcon, WalletIcon, VaspIcon, EvidenceIcon, ReportIcon } from "@/components/icons";
import { useApi } from "@/hooks/useApi";
import { investigations } from "@/api/investigations";
import { useDataSource } from "@/app/DataSourceContext";
import { useAuth } from "@/auth/AuthContext";
import { formatDate } from "@/lib/format";
import { InvestigatorAssistant } from "@/features/assistant/InvestigatorAssistant";
import type { InvestigationNote } from "@/api/types";
import type { TabItem } from "@/components/ui";

export function CaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isDemo } = useDataSource();
  const { user, can } = useAuth();

  const { data: investigation, loading, error, reload } = useApi(() => (id ? investigations.get(id) : Promise.resolve(null)), [id]);
  const { data: notes, reload: reloadNotes } = useApi<InvestigationNote[]>(() => (id ? investigations.notes(id) : Promise.resolve([])), [id]);
  const { data: timeline } = useApi(() => investigations.timeline(), []);

  const [tab, setTab] = useState("overview");
  const [noteText, setNoteText] = useState("");
  const [saving, setSaving] = useState(false);

  if (error) return <ErrorState title="Investigation is currently unavailable" description={error} action={<Button onClick={reload}>Retry</Button>} />;
  if (loading) return <SkeletonBlock rows={10} />;
  if (!investigation) {
    return (
      <div className="page">
        <EmptyState title="Investigation not found" description={`No case exists with ID ${id}.`} action={<Button onClick={() => navigate("/investigations")}>Back to investigations</Button>} />
      </div>
    );
  }

  const addNote = async () => {
    if (!noteText.trim() || !user || !id) return;
    setSaving(true);
    try {
      const author = user.name ?? user.username ?? "Analyst";
      await investigations.addNote(id, noteText.trim(), author);
      setNoteText("");
      reloadNotes();
    } finally {
      setSaving(false);
    }
  };

  const tabs: TabItem[] = [
    { key: "overview", label: "Overview" },
    { key: "notes", label: `Notes (${notes?.length ?? 0})` },
    { key: "timeline", label: `Timeline (${timeline?.length ?? 0})` },
    { key: "assistant", label: "Assistant" },
  ];

  return (
    <div className="page">
      <PageHeader
        title={investigation.name}
        subtitle={investigation.description}
        crumbs={[{ label: "Investigations", to: "/investigations" }, { label: investigation.id }]}
        actions={
          <>
            {isDemo || investigation.isDemo ? <DemoBadge /> : null}
            <RiskBadge level={investigation.risk} />
            <StatusBadge status={investigation.status} />
            {!isDemo ? <Button leading={<TraceIcon />} onClick={() => navigate(`/wallets?address=${encodeURIComponent(investigation.primaryWallet)}&case=${encodeURIComponent(investigation.id)}`)}>
              Analyze Wallet
            </Button> : null}
            <Button leading={<TraceIcon />} onClick={() => navigate(`/graph?address=${encodeURIComponent(investigation.primaryWallet)}`)}>
              Trace Funds
            </Button>
            <Button leading={<WalletIcon />} onClick={() => navigate(`/wallets/${encodeURIComponent(investigation.primaryWallet)}`)}>
              Open Wallet
            </Button>
            <Button leading={<VaspIcon />} onClick={() => navigate(`/vasp?case=${encodeURIComponent(investigation.id)}&wallet=${encodeURIComponent(investigation.primaryWallet)}`)}>
              Find VASP
            </Button>
            <Button leading={<EvidenceIcon />} onClick={() => navigate(`/evidence?case=${encodeURIComponent(investigation.id)}&wallet=${encodeURIComponent(investigation.primaryWallet)}`)}>
              Add Evidence
            </Button>
            <Button leading={<ReportIcon />} onClick={() => navigate(`/reports?case=${investigation.id}`)}>
              Generate Report
            </Button>
          </>
        }
      />

      <div className="grid grid-4">
        <Card title="Primary Wallet">
          <ShortAddress address={investigation.primaryWallet} />
          <p style={{ margin: "6px 0 0", fontSize: "var(--text-xs)", color: "var(--text-faint)" }}>Network: {investigation.network}</p>
        </Card>
        <Card title="Assigned Analyst">{investigation.assignedAnalyst}</Card>
        <Card title="Transactions / VASP / Evidence">
          <span className="mono" title="Transactions captured by the most recent analysis batch">
            {investigation.transactions} tx (latest analysis)
          </span>{" "}
          ·{" "}
          <span className="mono" title="Unique transactions persisted in the wallet store">
            {investigation.persistedTransactions != null ? `${investigation.persistedTransactions} persisted` : "—"}
          </span>{" "}
          · <span className="mono">{investigation.vaspCandidates}</span> candidates ·{" "}
          <span className="mono">{investigation.evidenceCount}</span> evidence
        </Card>
        <Card title="Dates">
          <div className="stack">
            <span className="text-dim">Created {formatDate(investigation.createdAt)}</span>
            <span className="text-dim">Updated {formatDate(investigation.updatedAt)}</span>
          </div>
        </Card>
      </div>

      {investigation.tags?.length ? (
        <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
          {investigation.tags.map((t) => (
            <Badge key={t}>{t}</Badge>
          ))}
        </div>
      ) : null}

      <Card title="Case workspace" actions={<Tabs tabs={tabs} active={tab} onChange={setTab} />}>
        {tab === "overview" ? (
          <div className="stack">
            <p style={{ margin: 0, color: "var(--text-muted)" }}>
              This workspace composes the wallet, graph, VASP, evidence, and reporting features available in this release. In live mode the case is
              persisted by the backend case store and a pipeline analysis can be attached to it; in demo mode the case object comes from the labeled
              synthetic adapter.
            </p>
            {can("investigation.update") ? (
              <Button variant="primary" onClick={() => navigate(can("report.export") ? `/reports?case=${investigation.id}` : `/graph?address=${encodeURIComponent(investigation.primaryWallet)}`)}>
                Go to reporting
              </Button>
            ) : null}
          </div>
        ) : tab === "notes" ? (
          <div className="stack">
            {(notes ?? []).map((n) => (
              <div key={n.id} className="timeline-item" style={{ listStyle: "none" }}>
                <div className="timeline-body">
                  <div className="timeline-title">{n.author}</div>
                  <div className="timeline-meta">
                    <span>{formatDate(n.createdAt)}</span>
                    {isDemo || investigation.isDemo ? <Badge className="badge-demo">Demo</Badge> : null}
                  </div>
                  <p style={{ margin: "6px 0 0" }}>{n.body}</p>
                </div>
              </div>
            ))}
            {can("investigation.update") ? (
              <form
                className="stack"
                onSubmit={(e) => {
                  e.preventDefault();
                  void addNote();
                }}
              >
                <Field label="Add analyst note" htmlFor={`note-${id}`}>
                  <Textarea
                    id={`note-${id}`}
                    rows={2}
                    value={noteText}
                    onChange={(e) => setNoteText(e.target.value)}
                    placeholder="Analyst note — persisted with this case and visible to its investigators."
                  />
                </Field>
                <div className="row">
                  <Button variant="primary" type="submit" disabled={saving || !noteText.trim()}>
                    {saving ? "Adding…" : "Add note"}
                  </Button>
                </div>
              </form>
            ) : null}
          </div>
        ) : (
          <SimpleTimeline
            items={(timeline ?? []).map((t) => ({
              id: t.id,
              at: t.at,
              actor: t.actor,
              title: t.action,
              meta: t.category ? <Badge>{t.category}</Badge> : undefined,
            }))}
          />
        )}
        {tab === "assistant" ? (
          can("investigation.read") ? (
            <InvestigatorAssistant caseId={investigation.id} walletAddress={investigation.primaryWallet} scope="case" />
          ) : (
            <Badge className="status-draft">Your role needs the investigation.read permission to use the assistant.</Badge>
          )
        ) : null}
      </Card>
    </div>
  );
}