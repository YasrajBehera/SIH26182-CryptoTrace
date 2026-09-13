import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./client", () => ({ client: { get: vi.fn() } }));
vi.mock("./config", () => ({ isDemoMode: () => false }));
vi.mock("@/mock", () => ({
  getDemoGraph: () => ({ nodes: [], edges: [] }),
  getDemoPath: () => ({ nodes: [], edges: [], metrics: {} }),
}));

import { client } from "./client";
import { graph, toWalletId } from "./graph";

const getMock = vi.mocked(client.get);

describe("graph node/edge id contract", () => {
  beforeEach(() => {
    getMock.mockReset();
    getMock.mockImplementation((url: string) => {
      if (url.includes("/bfs")) {
        return Promise.resolve({
          wallet_id: "eth:0xaa",
          max_depth: 2,
          nodes: [
            { wallet_id: "eth:0xaa", address: "0xaa", chain: "eth", depth: 0 },
            {
              wallet_id: "eth:0xbb",
              address: "0xbb",
              chain: "eth",
              depth: 1,
            },
          ],
          edges: [
            {
              source: "eth:0xaa",
              target: "eth:0xbb",
              tx_id: "eth:0x01",
              tx_hash: "0x01",
              chain: "eth",
              amount: "100",
              timestamp: 1704067200,
              block_number: 20698121,
            },
          ],
        });
      }
      if (url.includes("/temporal-flow")) {
        return Promise.resolve({
          wallet_id: "eth:0xaa",
          direction: "all",
          flows: [
            {
              tx_id: "eth:0x01",
              tx_hash: "0x01",
              chain: "eth",
              block_timestamp: 1704067200,
              amount: "100",
              source: "eth:0xaa",
              target: "eth:0xbb",
            },
          ],
        });
      }
      if (url.includes("/fund-flow")) {
        return Promise.resolve({
          source: "eth:0xaa",
          destination: "eth:0xbb",
          wallet_path: ["eth:0xaa", "eth:0xbb"],
          hop_count: 1,
          transactions: [
            {
              tx_hash: "0x01",
              chain: "eth",
              sender: "eth:0xaa",
              receiver: "eth:0xbb",
              amount: "100",
              timestamp: 1704067200,
            },
          ],
          found: true,
        });
      }
      return Promise.resolve({});
    });
  });

  it("normalizes addresses into chain:address wallet ids", () => {
    expect(toWalletId("0xAB", "ethereum")).toBe("eth:0xab");
    expect(toWalletId("0xAB", "bsc")).toBe("bsc:0xab");
  });

  it("builds nodes with full wallet ids but bare display addresses", async () => {
    const res = await graph.query({ address: "0xaa", network: "ethereum", depth: 2 });
    const ids = res.nodes.map((n) => n.id);
    expect(ids).toContain("eth:0xaa");
    expect(ids).toContain("eth:0xbb");
    const start = res.nodes.find((n) => n.id === "eth:0xaa");
    expect(start?.address).toBe("0xaa");
  });

  it("keeps edge endpoint ids identical to node ids", async () => {
    const res = await graph.query({ address: "0xaa", network: "ethereum", depth: 2 });
    for (const e of res.edges) {
      expect(res.nodes.some((n) => n.id === e.source)).toBe(true);
      expect(res.nodes.some((n) => n.id === e.target)).toBe(true);
    }
  });

  it("deduplicates the same transfer reported by bfs and temporal flow", async () => {
    const res = await graph.query({ address: "0xaa", network: "ethereum", depth: 2 });
    const matching = res.edges.filter((e) => e.transactionHash === "0x01");
    expect(matching.length).toBe(1);
    expect(matching[0].blockNumber).toBe(20698121);
  });

  it("maps fund-flow wallet path to full-id nodes with bare addresses", async () => {
    const res = await graph.path("0xaa", "0xbb");
    expect(res.nodes.map((n) => n.id)).toEqual(["eth:0xaa", "eth:0xbb"]);
    expect(res.nodes[0].address).toBe("0xaa");
  });
});