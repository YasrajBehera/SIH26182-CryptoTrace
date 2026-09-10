import { useNavigate } from "react-router-dom";
import type { Investigation } from "@/api/types";
import { DataTable } from "@/components/ui/DataTable";
import type { ColumnDef } from "@/components/ui/DataTable";
import { Badge, DemoBadge, RiskBadge, StatusBadge } from "@/components/ui/Badges";
import { ShortAddress } from "@/components/ui/Address";
import { formatDate, formatNumber } from "@/lib/format";

export const investigationColumns = (): ColumnDef<Investigation>[] => [
  {
    key: "id",
    header: "Case ID",
    cell: (c) => <strong style={{ color: "var(--primary-hover)" }}>{c.id}</strong>,
    sortValue: (c) => c.id,
  },
  {
    key: "name",
    header: "Investigation",
    cell: (c) => (
      <span>
        {c.name}
        {c.isDemo ? <span style={{ marginLeft: 6 }}><DemoBadge label="DEMO" /></span> : null}
        <span style={{ display: "block", color: "var(--text-faint)", fontSize: "var(--text-xs)" }}>
          {c.assignedAnalyst}
        </span>
      </span>
    ),
    sortValue: (c) => c.name,
  },
  {
    key: "wallet",
    header: "Primary Wallet",
    cell: (c) => <ShortAddress address={c.primaryWallet} />,
    sortValue: (c) => c.primaryWallet,
  },
  {
    key: "network",
    header: "Network",
    cell: (c) => <Badge>{c.network}</Badge>,
    sortValue: (c) => c.network,
  },
  {
    key: "risk",
    header: "Risk",
    cell: (c) => <RiskBadge level={c.risk} />,
    sortValue: (c) => c.risk,
  },
  {
    key: "transactions",
    header: "Tx",
    align: "right",
    cell: (c) => formatNumber(c.transactions),
    sortValue: (c) => c.transactions,
  },
  {
    key: "vasp",
    header: "VASP",
    align: "right",
    cell: (c) => formatNumber(c.vaspCandidates),
    sortValue: (c) => c.vaspCandidates,
  },
  {
    key: "evidence",
    header: "Evidence",
    align: "right",
    cell: (c) => formatNumber(c.evidenceCount),
    sortValue: (c) => c.evidenceCount,
  },
  {
    key: "status",
    header: "Status",
    cell: (c) => <StatusBadge status={c.status} />,
    sortValue: (c) => c.status,
  },
  {
    key: "updated",
    header: "Last Updated",
    cell: (c) => <span title={c.updatedAt}>{formatDate(c.updatedAt)}</span>,
    sortValue: (c) => c.updatedAt,
  },
];

export function InvestigationTable({
  investigations,
  rowClick = true,
  pagination,
}: {
  investigations: Investigation[];
  rowClick?: boolean;
  pagination?: { pageSize: number };
}) {
  const navigate = useNavigate();
  return (
    <DataTable
      rows={investigations}
      columns={investigationColumns()}
      rowKey={(c) => c.id}
      onRowClick={rowClick ? (c) => navigate(`/cases/${c.id}`) : undefined}
      pagination={pagination ?? { pageSize: 10 }}
      empty="No investigations yet. Create one to begin."
      testid="investigation-table"
    />
  );
}