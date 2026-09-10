import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageHeader, Button, Card, Badge, DemoBadge, RiskBadge, StatusBadge, ShortAddress, SkeletonBlock, EmptyState, ErrorState, SimpleTimeline, Textarea, Field, Tabs } from "@/components/ui";
import { TraceIcon, WalletIcon, VaspIcon, EvidenceIcon, ReportIcon } from "@/components/icons";
import { useApi } from "@/hooks/useApi";
import { investigations } from "@/api/investigations";
import { useDataSource } from "@/app/DataSourceContext";
import { useAuth } from "@/auth/AuthContext";
import { formatDate } from "@/lib/format";
import type { TabItem } from "@/components/ui";

export function CaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isDemo } = useDataSource();
  const { user, can } = useAuth();

  const { data: investigation, loading, error, reload } = useApi(() => (id ? investigations.get(id) : Promise.resolve(null)), [id]);
  const { data: notes } = useApi(() => investigations.notes(), []);
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

  const addNote = () => {
    if (!noteText.trim() || !user) return;
    setSaving(true);
    setTimeout(() => {
      setSaving(false);
      setNoteText("");
    }, 400);
  };

  const tabs: TabItem[] = [
    { key: "overview", label: "Overview" },
    { key: "notes", label: `Notes (${notes?.length ?? 0})` },
    { key: "timeline", label: `Timeline (${timeline?.length ?? 0})` },
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
            <Button leading={<TraceIcon />} onClick={() => navigate(`/graph?address=${encodeURIComponent(investigation.primaryWallet)}`)}>
              Trace Funds
            </Button>
            <Button leading={<WalletIcon />} onClick={() => navigate(`/wallets/${encodeURIComponent(investigation.primaryWallet)}`)}>
              Open Wallet
            </Button>
            <Button leading={<VaspIcon />} onClick={() => navigate(`/vasp?wallet=${encodeURIComponent(investigation.primaryWallet)}`)}>
              Find VASP
            </Button>
            <Button leading={<EvidenceIcon />} onClick={() => navigate(`/evidence?wallet=${encodeURIComponent(investigation.primaryWallet)}`)}>
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
          <span className="mono">{investigation.transactions} tx</span> ·{" "}
          <span className="mono">{investigation.vaspCandidates}</span> candidates ·{" "}
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
              This is a demo workspace that composes the wallet, graph, VASP, evidence, and reporting features available in this release. Backend case
              persistence is pending; today the case object is provided by the labeled synthetic adapter.
            </p>
            {can("investigation.update") ? (
              <Button variant="primary" onClick={() => navigate(`/reports?case=${investigation.id}`)}>
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
                    <Badge className="badge-demo">Demo</Badge>
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
                  addNote();
                }}
              >
                <Field label="Add analyst note" htmlFor={`note-${id}`}>
                  <Textarea id={`note-${id}`} rows={2} value={noteText} onChange={(e) => setNoteText(e.target.value)} placeholder="Optional note — notes are persisted server-side in a later release." />
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
      </Card>
    </div>
  );
}