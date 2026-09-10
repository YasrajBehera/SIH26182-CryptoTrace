import type { BlockchainTransfer } from "@/api/types";
import { Drawer, Address, Badge } from "@/components/ui";
import { directionBadge } from "./TransferTable";
import { formatAmount, formatDate, formatNumber } from "@/lib/format";

export function TransferDrawer({
  transfer,
  onClose,
}: {
  transfer: BlockchainTransfer | null;
  onClose: () => void;
}) {
  return (
    <Drawer
      open={!!transfer}
      onClose={onClose}
      title={transfer ? "Transaction details" : ""}
      labelledBy="tx-drawer-title"
      wide
    >
      {transfer ? (
        <>
          <div className="row">
            {directionBadge(transfer.direction)}
            <Badge>{transfer.asset}</Badge>
            <Badge className="status-draft">Block {formatNumber(transfer.block_number ?? undefined)}</Badge>
            <Badge className="status-draft">{transfer.category}</Badge>
          </div>

          <div className="detail-grid">
            <div className="stack">
              <DetailRow label="Transaction hash" value={<code className="mono" style={{ fontSize: 11.5 }}>{transfer.transaction_hash}</code>} monoRight />
              <DetailRow label="Block timestamp" value={formatDate(transfer.block_timestamp)} />
              <DetailRow label="From" value={<Address address={transfer.from_address} chain={transfer.chain} />} />
              <DetailRow label="To" value={<Address address={transfer.to_address} chain={transfer.chain} />} />
              <DetailRow label="Amount" value={<strong>{formatAmount(transfer.value, transfer.asset)}</strong>} />
            </div>
            <div className="stack">
              <DetailRow label="Direction" value={transfer.direction === "in" ? "Incoming (to wallet)" : "Outgoing (from wallet)"} />
              <DetailRow label="Network" value={transfer.chain} />
              {transfer.raw_contract_address ? (
                <DetailRow label="Token contract" value={<span className="mono" style={{ fontSize: 11.5 }}>{transfer.raw_contract_address}</span>} />
              ) : null}
              {transfer.raw_contract_value ? (
                <DetailRow label="Raw contract value" value={<span className="mono">{transfer.raw_contract_value}</span>} />
              ) : null}
              <DetailRow label="USD value" value="—" />
            </div>
          </div>

          <div className="stack">
            <h3 className="card-title-sm">Investigation context</h3>
            <div className="detail-row">
              <span className="detail-label">Related case</span>
              <span className="detail-value">Attach to a case from the investigations page.</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Risk indicators</span>
              <span className="detail-value">None computed — no risk engine connected ({transfer.chain}).</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Evidence</span>
              <span className="detail-value">No evidence linked.</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Confirmations</span>
              <span className="detail-value">≥ 1 (recorded on-chain)</span>
            </div>
          </div>

          <div className="card" style={{ background: "var(--bg-elevated)" }}>
            <p style={{ margin: 0, fontSize: "var(--text-xs)", color: "var(--text-faint)" }}>
              This record follows the normalized transfer schema from the Member 1 ingestion layer. USD valuation
              and per-transaction risk require additional backend support.
            </p>
          </div>
        </>
      ) : null}
    </Drawer>
  );
}

export function DetailRow({
  label,
  value,
  monoRight,
}: {
  label: string;
  value: React.ReactNode;
  monoRight?: boolean;
}) {
  return (
    <div className="detail-row">
      <span className="detail-label">{label}</span>
      <span className={`detail-value ${monoRight ? "mono" : ""}`}>{value}</span>
    </div>
  );
}