import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { PageHeader, Button, Card, Badge, DemoBadge, RiskBadge, StatusBadge, Address, Input, Select, Field, SkeletonBlock, EmptyState, ErrorState, UnauthorizedState, useToast } from "@/components/ui";
import { TraceIcon, WalletIcon, VaspIcon, EvidenceIcon, ReportIcon } from "@/components/icons";
import { useApi } from "@/hooks/useApi";
import { wallets } from "@/api/wallets";
import { useDataSource } from "@/app/DataSourceContext";
import { useAuth } from "@/auth/AuthContext";
import type { WalletSummary } from "@/api/types";
import { TransferTable } from "@/components/transfers/TransferTable";
import { TransferDrawer } from "@/components/transfers/TransferDrawer";
import type { BlockchainTransfer } from "@/api/types";
import { formatAmount } from "@/lib/format";
import { validateAddressInput } from "@/lib/address";
import { InvestigatorAssistant } from "@/features/assistant/InvestigatorAssistant";

export function WalletDetailPage() {
  const { address: rawAddress } = useParams<{ address: string }>();
  const address = useMemo(() => rawAddress?.trim().toLowerCase() ?? "", [rawAddress]);
  const navigate = useNavigate();
  const { isDemo } = useDataSource();
  const { can } = useAuth();
  const { push } = useToast();

  const copyAddress = async () => {
    try {
      await navigator.clipboard.writeText(address);
      push({ kind: "ok", title: "Address copied", description: "Copied to clipboard." });
    } catch {
      push({ kind: "warn", title: "Copy failed", description: "Clipboard access is blocked in this browser." });
    }
  };

  const [page, setPage] = useState(0);
  const PAGE_SIZE = 25;
  // Filters (direction is applied server-side so it stays consistent with the
  // persisted page offset; the other filters are local to the loaded page).
  const [q, setQ] = useState("");
  const [direction, setDirection] = useState("all");
  const [asset, setAsset] = useState("all");
  const [minAmount, setMinAmount] = useState("");

  const { data: summary, loading: summaryLoading } = useApi<WalletSummary | null>(() => wallets.getSummary(address), [address]);
  const { data: walletData, loading, error, reload } = useApi(
    () =>
      wallets.getTransfers(address, PAGE_SIZE, {
        offset: page * PAGE_SIZE,
        direction: direction === "all" ? undefined : (direction as "in" | "out"),
      }),
    [address, page, direction],
  );

  const [selected, setSelected] = useState<BlockchainTransfer | null>(null);

  const transfers = useMemo(() => walletData?.transfers ?? [], [walletData]);
  const pagination = walletData?.pagination;
  const total = pagination?.total ?? 0;
  const source = pagination?.source ?? "provider";
  const truncated = pagination?.truncated ?? false;
  const assets = useMemo(() => Array.from(new Set(transfers.map((t) => t.asset))).sort(), [transfers]);

  const filtered = useMemo(() => {
    return transfers.filter((t) => {
      if (q && !t.transaction_hash.toLowerCase().includes(q.toLowerCase())) return false;
      if (direction !== "all" && t.direction !== direction) return false;
      if (asset !== "all" && t.asset !== asset) return false;
      if (minAmount && (Number(t.value) || 0) < Number(minAmount)) return false;
      return true;
    });
  }, [transfers, q, direction, asset, minAmount]);

  const volumes = useMemo(() => {
    let inc = 0;
    let out = 0;
    transfers.forEach((t) => {
      const v = Number(t.value) || 0;
      if (t.direction === "in") inc += v;
      else out += v;
    });
    return { inc, out };
  }, [transfers]);

  if (!can("wallet.read")) {
    return (
      <div className="page">
        <PageHeader title="Wallet Investigation" />
        <UnauthorizedState />
      </div>
    );
  }

  if (validateAddressInput(address)) {
    return (
      <div className="page">
        <ErrorState title="Invalid wallet address" description="The address must be a valid 0x… (40 hex characters) public address." />
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        title="Wallet Investigation"
        subtitle={`${address.slice(0, 6)}…${address.slice(-4)} on Ethereum${isDemo ? " — demo data" : ""}`}
        crumbs={[{ label: "Wallet Explorer", to: "/wallets" }, { label: address.slice(0, 10) }]}
        actions={
          <>
            {isDemo ? <DemoBadge label="DEMO WALLET DATA" /> : <Badge className="status-success">Live ingestion</Badge>}
            <Button leading={<TraceIcon />} onClick={() => navigate(`/graph?address=${encodeURIComponent(address)}`)}>
              Trace Funds
            </Button>
            <Button leading={<WalletIcon />} onClick={() => navigate(`/graph?address=${encodeURIComponent(address)}`)}>
              Build Graph
            </Button>
            <Button leading={<VaspIcon />} onClick={() => navigate(`/vasp?wallet=${encodeURIComponent(address)}`)}>
              Find VASP
            </Button>
            <Button leading={<EvidenceIcon />} onClick={() => navigate(`/evidence?wallet=${encodeURIComponent(address)}`)}>
              Add Evidence
            </Button>
            <Button leading={<ReportIcon />} onClick={() => navigate(`/reports?wallet=${encodeURIComponent(address)}`)}>
              Create Report
            </Button>
          </>
        }
      />

      {/* Wallet overview stats */}
      <div className="grid grid-4">
        <Card title="Address">
          <div className="row" style={{ gap: 8, alignItems: "center" }}>
            <Address address={address} chain="eth" head={10} tail={8} />
            <Button variant="ghost" size="sm" onClick={copyAddress}>
              Copy
            </Button>
          </div>
          <p style={{ margin: "8px 0 0", fontSize: "var(--text-xs)", color: "var(--text-faint)" }}>
            First seen: {summary?.firstSeen ? new Date(summary.firstSeen).toLocaleDateString() : "—"}
            <br />
            Last activity: {summary?.lastActivity ? new Date(summary.lastActivity).toLocaleDateString() : "—"}
          </p>
        </Card>
        <Card title={source === "database" ? "Persisted transactions" : "Latest ingestion"} subtitle={summaryLoading ? "loading…" : undefined}>
          <div style={{ fontSize: 24, fontWeight: 700 }}>
            {(source === "database" ? total : transfers.length).toLocaleString()}
          </div>
          <p style={{ margin: "6px 0 0", fontSize: "var(--text-xs)", color: "var(--text-faint)" }}>
            {source === "database"
              ? "Held in the persisted investigation store — consistent across surfaces."
              : "New/returned transfers from the latest blockchain ingestion."}
          </p>
        </Card>
        <Card title="Volume">
          <div className="stack" style={{ gap: 4 }}>
            <div className="detail-row" style={{ borderBottom: 0, padding: 0 }}>
              <span className="detail-label">Incoming</span>
              <span className="detail-value mono">{formatAmount(volumes.inc)}</span>
            </div>
            <div className="detail-row" style={{ borderBottom: 0, padding: 0 }}>
              <span className="detail-label">Outgoing</span>
              <span className="detail-value mono">{formatAmount(volumes.out)}</span>
            </div>
            <div className="detail-row" style={{ borderBottom: 0, padding: 0 }}>
              <span className="detail-label">Reported balance</span>
              <span className="detail-value">{summary?.balance ? formatAmount(summary.balance) : "—"}</span>
            </div>
          </div>
        </Card>
        <Card title="Assessment">
          <div className="stack" style={{ gap: 8 }}>
            <div>
              <div className="detail-label" style={{ marginBottom: 4 }}>Risk</div>
              <RiskBadge level={summary?.risk ?? "unknown"} />
            </div>
            <div>
              <div className="detail-label" style={{ marginBottom: 4 }}>Status</div>
              {!summary || summary.investigationStatus === "not_analyzed" ? (
                <Badge className="status-draft">Not analyzed</Badge>
              ) : summary.investigationStatus === "pending" ? (
                <Badge className="status-pending">Analysis pending</Badge>
              ) : (
                <StatusBadge status={summary.investigationStatus} />
              )}
            </div>
          </div>
        </Card>
      </div>

      {/* Transfers */}
      <Card
        title="Transaction history"
        subtitle={
          <>
            <span data-testid="tx-history-label">
              {source === "database"
                ? `Persisted investigation history: ${total} held transfers`
                : transfers.length === 0
                  ? "Latest ingestion returned no transfers"
                  : `Latest ingestion: ${transfers.length} new/returned transfers`}
            </span>
            {typeof total === "number" && total > 0
              ? ` — page ${page + 1} of ${Math.max(1, Math.ceil(total / PAGE_SIZE))}`
              : null}
            {source === "database" ? (
              <span className="status-ok" style={{ marginLeft: 8 }} title="Served from the persisted PostgreSQL wallet store — consistent across surfaces.">
                from DB
              </span>
            ) : (
              <span className="status-warn" style={{ marginLeft: 8 }} title="Fetched fresh from the blockchain provider for this request.">
                provider-fetched
              </span>
            )}
            {truncated && typeof total === "number" ? (
              <Badge className="status-warn" title="On-chain history may extend beyond the persisted set for this wallet.">
                First {total} ingested
              </Badge>
            ) : null}
          </>
        }
        actions={
          <span className="row" style={{ gap: 6 }}>
            <Button variant="ghost" size="sm" onClick={reload}>↻ Refresh</Button>
            <Link to={`/transactions?wallet=${encodeURIComponent(address)}`} className="btn btn-ghost btn-sm">
              Open in explorer
            </Link>
          </span>
        }
      >
        <div className="table-toolbar">
          <Input
            className="mono"
            style={{ maxWidth: 260 }}
            placeholder="Filter by transaction hash…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Filter by transaction hash"
          />
          <Select
            value={direction}
            onChange={(e) => {
              setDirection(e.target.value);
              setPage(0);
            }}
            aria-label="Filter by direction"
            style={{ maxWidth: 150 }}
          >
            <option value="all">All directions</option>
            <option value="in">Incoming</option>
            <option value="out">Outgoing</option>
          </Select>
          <Select value={asset} onChange={(e) => setAsset(e.target.value)} aria-label="Filter by asset" style={{ maxWidth: 150 }}>
            <option value="all">All assets</option>
            {assets.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </Select>
          <Field label="" htmlFor="min-amount">
            <Input
              id="min-amount"
              type="number"
              style={{ maxWidth: 130 }}
              placeholder="Min amount"
              value={minAmount}
              onChange={(e) => setMinAmount(e.target.value)}
              aria-label="Minimum amount"
            />
          </Field>
        </div>

        {loading ? (
          <SkeletonBlock rows={8} />
        ) : error ? (
          <ErrorState
            title="Blockchain data is currently unavailable"
            description={error}
            action={<Button variant="primary" onClick={reload}>Retry</Button>}
          />
        ) : transfers.length === 0 ? (
          <EmptyState title="No transfers found" description="This wallet has no normalized transfers in the current dataset." />
        ) : (
          <>
          <TransferTable transfers={filtered} demo={isDemo} onRowClick={setSelected} pagination={{ pageSize: 15 }} />
          {typeof total === "number" ? (
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12, flexWrap: "wrap" }}>
              <Button
                variant="ghost"
                size="sm"
                disabled={!pagination?.has_previous}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                ← Previous
              </Button>
              <span className="text-dim" style={{ fontSize: "var(--text-sm)" }}>
                {transfers.length > 0
                  ? `Rows ${(pagination?.offset ?? 0) + 1}–${(pagination?.offset ?? 0) + transfers.length}`
                  : "No rows"}
                {typeof total === "number" ? ` of ${total}` : ""} held transfers
              </span>
              <Button
                variant="ghost"
                size="sm"
                disabled={!pagination?.has_next}
                onClick={() => setPage((p) => p + 1)}
              >
                Next →
              </Button>
            </div>
          ) : null}
          </>
        )}
      </Card>

      <TransferDrawer transfer={selected} onClose={() => setSelected(null)} demo={isDemo} />

      {can("investigation.read") ? (
        <InvestigatorAssistant walletAddress={address} scope="wallet" compact />
      ) : null}
    </div>
  );
}