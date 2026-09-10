import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RiskBadge, StatusBadge, DemoBadge } from "@/components/ui/Badges";
import { TransferTable } from "@/components/transfers/TransferTable";
import type { BlockchainTransfer } from "@/api/types";
import { DataTable } from "@/components/ui/DataTable";

function makeTransfer(overrides: Partial<BlockchainTransfer> = {}): BlockchainTransfer {
  return {
    transaction_hash: `0x${"ab".repeat(32)}`,
    block_number: 19345310,
    block_timestamp: "2026-01-02T10:00:00Z",
    from_address: "0x" + "11".repeat(20),
    to_address: "0x" + "22".repeat(20),
    value: "5000000",
    asset: "USDT",
    category: "erc20",
    direction: "in",
    raw_contract_address: "0x" + "33".repeat(20),
    raw_contract_value: "0x4c4b40",
    chain: "eth",
    ...overrides,
  };
}

describe("Badge components", () => {
  it("renders risk badges with level-labeled text", () => {
    render(<RiskBadge level="critical" />);
    expect(screen.getByText("Critical")).toBeInTheDocument();
  });

  it("renders status labels", () => {
    render(<StatusBadge status="investigating" />);
    expect(screen.getByText("Investigating")).toBeInTheDocument();
  });

  it("renders DEMO indicator and its tooltip title", () => {
    render(<DemoBadge label="DEMO WALLET" />);
    expect(screen.getByText("DEMO WALLET")).toBeInTheDocument();
    expect(screen.getByTitle(/synthetic demo data/i)).toBeInTheDocument();
  });
});

describe("TransferTable", () => {
  const rows = [makeTransfer({ transaction_hash: "0x" + "a0".repeat(32), value: "100" }), makeTransfer({ direction: "out", value: "200", asset: "ETH" })];

  it("renders a DEMO banner and transfer rows", () => {
    render(<TransferTable transfers={rows} demo />);
    expect(screen.getByText(/SYNTHETIC TRANSFERS/i)).toBeInTheDocument();
    expect(screen.getAllByRole("row").length).toBeGreaterThan(0);
  });

  it("calls onRowClick handler", async () => {
    const onRowClick = vi.fn();
    render(<TransferTable transfers={rows} onRowClick={onRowClick} pagination={{ pageSize: 10 }} />);
    const user = userEvent.setup();
    await user.click(screen.getAllByRole("row")[1]);
    expect(onRowClick).toHaveBeenCalledTimes(1);
  });

  it("shows empty message when no transfers", () => {
    render(<TransferTable transfers={[]} />);
    expect(screen.getByText(/No transfers match/i)).toBeInTheDocument();
  });
});

describe("DataTable", () => {
  it("sorts rows when a sortable column header is clicked", async () => {
    const user = userEvent.setup();
    render(
      <DataTable
        rows={[{ v: 2 }, { v: 1 }]}
        rowKey={(r) => String(r.v)}
        columns={[{ key: "v", header: "Value", cell: (r) => String(r.v), sortValue: (r) => r.v }]}
        pagination={{ pageSize: 5 }}
        testid="sort-table"
      />,
    );
    const table = screen.getByTestId("sort-table");
    const rowsBefore = within(table).getAllByRole("row").map((r) => r.textContent);
    await user.click(within(table).getByText("Value"));
    const rowsAfter = within(table).getAllByRole("row").map((r) => r.textContent);
    expect(rowsAfter).not.toEqual(rowsBefore);
  });
});