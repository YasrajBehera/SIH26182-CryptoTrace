import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { PageHeader, Card, Button, Input, Select, DemoBadge, Badge, EmptyState, ErrorState, SkeletonBlock, Field, UnauthorizedState } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { wallets } from "@/api/wallets";
import { useDataSource } from "@/app/DataSourceContext";
import { useAuth } from "@/auth/AuthContext";
import { TransferTable } from "@/components/transfers/TransferTable";
import { TransferDrawer } from "@/components/transfers/TransferDrawer";
import type { BlockchainTransfer, WalletTransfers } from "@/api/types";
import { validateAddressInput } from "@/lib/address";
import { demoWallets } from "@/mock";
import { ShortAddress } from "@/components/ui";

const PAGE_SIZE = 25;

export function TransactionsPage() {
  const [params, setParams] = useSearchParams();
  const walletParam = params.get("wallet") ?? "";
  const [wallet, setWalletState] = useState(walletParam);
  const [submitted, setSubmitted] = useState(walletParam);
  const { isDemo } = useDataSource();
  const { can } = useAuth();

  // Server-side pagination (LIVE mode): the backend slices the sorted held
  // transfer set; offset/has_next/has_previous come back in `pagination`.
  // DEMO mode sidesteps the backend entirely (labeled synthetic data).
  const [offset, setOffset] = useState(0);
  const [direction, setDirection] = useState<"all" | "in" | "out">("all");
  const serverPaginated = !isDemo && !!submitted && validateAddressInput(submitted) === null;

  const { data, loading, error, reload } = useApi<WalletTransfers | null>(
    () =>
      submitted && validateAddressInput(submitted) === null
        ? wallets.getTransfers(submitted, PAGE_SIZE, {
            offset,
            direction: direction === "all" ? undefined : direction,
          })
        : Promise.resolve(null),
    [submitted, offset, direction],
  );

  // Client-side filters (applied within the loaded page)
  const [q, setQ] = useState(params.get("hash") ?? "");
  const [asset, setAsset] = useState("all");
  const [chain, setChain] = useState("all");
  const [minAmount, setMinAmount] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  const [selected, setSelected] = useState<BlockchainTransfer | null>(null);

  const transfers = useMemo(() => data?.transfers ?? [], [data]);
  const pagination = data?.pagination;
  const assets = useMemo(
    () => Array.from(new Set(transfers.map((t) => t.asset))).sort(),
    [transfers],
  );
  const chains = useMemo(
    () => Array.from(new Set(transfers.map((t) => t.chain))).sort(),
    [transfers],
  );

  const filtered = useMemo(
    () =>
      transfers.filter((t) => {
        if (q && !t.transaction_hash.toLowerCase().includes(q.toLowerCase())) return false;
        if (!serverPaginated && direction !== "all" && t.direction !== direction) return false;
        if (asset !== "all" && t.asset !== asset) return false;
        if (chain !== "all" && t.chain !== chain) return false;
        if (minAmount && (Number(t.value) || 0) < Number(minAmount)) return false;
        if (fromDate && t.block_timestamp && new Date(t.block_timestamp) < new Date(`${fromDate}T00:00:00Z`)) {
          return false;
        }
        if (toDate && t.block_timestamp && new Date(t.block_timestamp) > new Date(`${toDate}T23:59:59Z`)) {
          return false;
        }
        return true;
      }),
    [transfers, q, direction, asset, chain, minAmount, fromDate, toDate, serverPaginated],
  );

  const hasFilters = q || asset !== "all" || chain !== "all" || minAmount || fromDate || toDate;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validateAddressInput(wallet) !== null) return;
    setSubmitted(wallet);
    setOffset(0);
    setParams({ wallet });
  };

  const invalid = wallet ? validateAddressInput(wallet) : null;

  if (!can("wallet.read")) {
    return (
      <div className="page">
        <PageHeader title="Transaction Explorer" />
        <UnauthorizedState />
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        title="Transaction Explorer"
        subtitle="Search and filter normalized transfers across investigated wallets."
        crumbs={[{ label: "Transactions" }]}
      />

      <Card title="Wallet source" subtitle="Load transfers for a wallet before exploring transactions.">
        <form className="stack" onSubmit={submit}>
          <Field label="Wallet address" htmlFor="txp-address" error={invalid ?? undefined}>
            <div className="input-group">
              <Input
                id="txp-address"
                className="mono"
                placeholder="0x…"
                value={wallet}
                invalid={!!invalid}
                onChange={(e) => setWalletState(e.target.value)}
              />
              <Button variant="primary" type="submit">
                Load transfers
              </Button>
            </div>
          </Field>
          <div className="row">
            <span style={{ color: "var(--text-faint)", fontSize: "var(--text-sm)" }}>Try a demo wallet:</span>
            {demoWallets.slice(0, 3).map((w) => (
              <button
                key={w}
                className="chip"
                type="button"
                onClick={() => {
                  setWalletState(w);
                  setSubmitted(w);
                  setOffset(0);
                  setParams({ wallet: w });
                }}
              >
                <ShortAddress address={w} />
              </button>
            ))}
          </div>
        </form>
      </Card>

      <div className="table-toolbar">
        <DemoBadge label={isDemo ? "DEMO TRANSFERS ACTIVE" : "LIVE"} />
        <Input
          className="mono"
          style={{ maxWidth: 240 }}
          placeholder="Filter by hash…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Filter by transaction hash"
        />
        <Select
          value={direction}
          onChange={(e) => {
            setDirection(e.target.value as "all" | "in" | "out");
            setOffset(0);
          }}
          aria-label="Direction"
          style={{ maxWidth: 170 }}
        >
          <option value="all">Incoming + outgoing</option>
          <option value="in">Incoming</option>
          <option value="out">Outgoing</option>
        </Select>
        <Select value={asset} onChange={(e) => setAsset(e.target.value)} aria-label="Asset" style={{ maxWidth: 130 }}>
          <option value="all">All assets</option>
          {assets.map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </Select>
        <Select value={chain} onChange={(e) => setChain(e.target.value)} aria-label="Chain" style={{ maxWidth: 120 }}>
          <option value="all">All chains</option>
          {chains.map((c) => (
            <option key={c} value={c}>{c.toUpperCase()}</option>
          ))}
        </Select>
        <Input
          type="number"
          style={{ maxWidth: 120 }}
          placeholder="Min amount"
          value={minAmount}
          onChange={(e) => setMinAmount(e.target.value)}
          aria-label="Minimum amount"
        />
        <Input
          type="date"
          style={{ maxWidth: 150 }}
          value={fromDate}
          onChange={(e) => setFromDate(e.target.value)}
          aria-label="From date"
        />
        <span className="text-dim" aria-hidden>→</span>
        <Input
          type="date"
          style={{ maxWidth: 150 }}
          value={toDate}
          onChange={(e) => setToDate(e.target.value)}
          aria-label="To date"
        />
        <span className="spacer" />
        {submitted ? (
          <Badge className="status-open">
            Wallet: <span className="mono">{submitted.slice(0, 10)}…</span>
          </Badge>
        ) : null}
        <Button variant="ghost" size="sm" onClick={reload}>
          ↻ Refresh
        </Button>
      </div>

      {loading ? (
        <SkeletonBlock rows={10} />
      ) : error ? (
        <ErrorState title="Blockchain data is currently unavailable" description={error} action={<Button onClick={reload}>Retry</Button>} />
      ) : !submitted ? (
        <EmptyState
          title="No wallet selected"
          description="Enter a wallet address (or pick a demo wallet) to load its normalized transfers and explore them here."
        />
      ) : transfers.length === 0 ? (
        <EmptyState title="No transfers" description="No normalized transfers returned for this wallet." />
      ) : (
        <>
          {serverPaginated && hasFilters ? (
            <div style={{ marginBottom: 8, color: "var(--text-dim)", fontSize: "var(--text-sm)" }}>
              Filters apply within the currently loaded page. The direction filter is applied server-side and preserved
              across pages.
            </div>
          ) : null}
          <TransferTable
            transfers={filtered}
            demo={isDemo}
            onRowClick={setSelected}
            clientPagination={!serverPaginated}
          />
          {serverPaginated ? (
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12, flexWrap: "wrap" }}>
              <Button
                variant="ghost"
                size="sm"
                disabled={!pagination?.has_previous}
                onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
              >
                ← Previous
              </Button>
              <span className="text-dim" style={{ fontSize: "var(--text-sm)" }}>
                {transfers.length > 0
                  ? `Rows ${(pagination?.offset ?? 0) + 1}–${(pagination?.offset ?? 0) + transfers.length}`
                  : "No rows"}
                {typeof pagination?.total === "number" ? ` of ${pagination.total}` : ""} held transfers
              </span>
              <Button
                variant="ghost"
                size="sm"
                disabled={!pagination?.has_next}
                onClick={() => setOffset((o) => o + PAGE_SIZE)}
              >
                Next →
              </Button>
              {pagination?.truncated ? (
                <Badge className="status-warn" title="On-chain history may extend beyond the provider fetch cap.">
                  Truncated
                </Badge>
              ) : null}
            </div>
          ) : null}
        </>
      )}

      <TransferDrawer transfer={selected} onClose={() => setSelected(null)} demo={isDemo} />
    </div>
  );
}