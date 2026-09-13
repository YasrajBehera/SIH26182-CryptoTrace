import { describe, expect, it } from "vitest";
import { getDemoTransfers } from "./transfers";
import { demoWallets } from "./transfers";

describe("getDemoTransfers (synthetic, labeled)", () => {
  it("serves pages by offset/limit with stable pagination metadata", () => {
    const first = getDemoTransfers(demoWallets[0], 40, 0);
    const second = getDemoTransfers(demoWallets[0], 40, 20);

    expect(first.transfers).toHaveLength(40);
    expect(second.transfers).toHaveLength(40);
    expect(first.transfers[0].transaction_hash).not.toBe(second.transfers[0].transaction_hash);
    expect(first.pagination.offset).toBe(0);
    expect(second.pagination.offset).toBe(20);
    expect(second.pagination.total).toBe(64);
    expect(second.pagination.has_previous).toBe(true);
    expect(second.pagination.has_next).toBe(true);
    expect(first.pagination.has_previous).toBe(false);
    expect(first.pagination.truncated).toBe(false);
  });

  it("reports a final page with has_next false", () => {
    const last = getDemoTransfers(demoWallets[0], 40, 40);
    expect(last.transfers).toHaveLength(24);
    expect(last.pagination.has_next).toBe(false);
    expect(last.pagination.has_previous).toBe(true);
  });

  it("applies the direction filter and keeps across pages", () => {
    const page = getDemoTransfers(demoWallets[0], 500, 0, "out");
    expect(page.transfers.length).toBeGreaterThan(0);
    expect(page.transfers.every((t) => t.direction === "out")).toBe(true);
    expect(page.pagination.total).toBeGreaterThan(0);
  });

  it("sorts ascending by timestamp", () => {
    const page = getDemoTransfers(demoWallets[1], 500, 0);
    const times = page.transfers.map((t) => new Date(t.block_timestamp!).getTime());
    expect(times).toEqual([...times].sort((a, b) => a - b));
  });
});