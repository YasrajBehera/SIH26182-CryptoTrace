import type { BlockchainTransfer } from "@/api/types";
import { DataTable } from "@/components/ui/DataTable";
import type { ColumnDef } from "@/components/ui/DataTable";
import { Badge, DemoBadge } from "@/components/ui/Badges";
import { ShortAddress } from "@/components/ui/Address";
import { formatDate, formatAmount, formatUsd } from "@/lib/format";
import { shortenHash } from "@/lib/format";
import { estimateUsd } from "@/api/marketdata";
import { useEthPrice } from "@/hooks/useEthPrice";

const DIRECTION_COLOR: Record<string, string> = {
  in: "status-success",
  out: "status-escalated",
};

export function directionBadge(direction: BlockchainTransfer["direction"]) {
  return <Badge className={DIRECTION_COLOR[direction]}>{direction === "in" ? "Incoming" : "Outgoing"}</Badge>;
}

export const transferColumns = (priceUsd?: number | null): ColumnDef<BlockchainTransfer>[] => [
  {
    key: "hash",
    header: "Transaction",
    cell: (t) => (
      <code className="mono" style={{ color: "var(--cyan)" }}>{shortenHash(t.transaction_hash, 12, 8)}</code>
    ),
    sortValue: (t) => t.transaction_hash,
  },
  {
    key: "timestamp",
    header: "Timestamp",
    cell: (t) => <span title={t.block_timestamp ?? undefined}>{formatDate(t.block_timestamp)}</span>,
    sortValue: (t) => t.block_timestamp ?? "",
  },
  {
    key: "direction",
    header: "Direction",
    cell: (t) => directionBadge(t.direction),
    sortValue: (t) => t.direction,
  },
  {
    key: "from",
    header: "From",
    cell: (t) => <ShortAddress address={t.from_address} />,
    sortValue: (t) => t.from_address,
  },
  {
    key: "to",
    header: "To",
    cell: (t) => <ShortAddress address={t.to_address} />,
    sortValue: (t) => t.to_address,
  },
  {
    key: "asset",
    header: "Asset",
    cell: (t) => <Badge>{t.asset}</Badge>,
    sortValue: (t) => t.asset,
  },
  {
    key: "amount",
    header: "Amount",
    align: "right",
    cell: (t) => <strong className="mono">{formatAmount(t.value)}</strong>,
    sortValue: (t) => Number(t.value) || 0,
  },
  {
    key: "usd",
    header: "≈ USD",
    align: "right",
    cell: (t) => {
      const v = estimateUsd(t.value, priceUsd ?? null, t.asset);
      return v !== null ? (
        <span className="mono" style={{ color: "var(--text-muted)" }} title="Reference-rate estimate">{formatUsd(v)}</span>
      ) : (
        <span className="mono" style={{ color: "var(--text-faint)" }} title="No reference rate for this asset">—</span>
      );
    },
    sortValue: (t) => estimateUsd(t.value, priceUsd ?? null, t.asset) ?? 0,
  },
  {
    key: "block",
    header: "Block",
    align: "right",
    cell: (t) => <span className="mono">{t.block_number ?? "—"}</span>,
    sortValue: (t) => t.block_number ?? 0,
  },
  {
    key: "category",
    header: "Category",
    cell: (t) => <span style={{ color: "var(--text-muted)" }}>{t.category}</span>,
    sortValue: (t) => t.category,
  },
  {
    key: "status",
    header: "Status",
    cell: () => <Badge className="status-draft">Recorded</Badge>,
  },
];

export interface TransferTableProps {
  transfers: BlockchainTransfer[];
  demo?: boolean;
  onRowClick?: (t: BlockchainTransfer) => void;
  pagination?: { pageSize: number };
}

export function TransferTable({ transfers, demo, onRowClick, pagination }: TransferTableProps) {
  const priceUsd = useEthPrice();
  return (
    <div>
      {demo ? (
        <div style={{ marginBottom: 8 }}>
          <DemoBadge label="SYNTHETIC TRANSFERS — not on-chain" />
        </div>
      ) : null}
      <DataTable
        rows={transfers}
        columns={transferColumns(priceUsd)}
        rowKey={(t) => `${t.transaction_hash}-${t.direction}-${t.from_address}-${t.to_address}`}
        onRowClick={onRowClick}
        pagination={pagination ?? { pageSize: 15 }}
        empty="No transfers match the current filters."
        initialSort={{ key: "timestamp", dir: "desc" }}
        testid="transfer-table"
      />
    </div>
  );
}