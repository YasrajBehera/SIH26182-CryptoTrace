import { describe, expect, it } from "vitest";
import { getDemoSearchResults } from "./search";

describe("getDemoSearchResults (synthetic, labeled)", () => {
  it("returns empty results for a blank term", () => {
    const res = getDemoSearchResults("");
    expect(res.total).toBe(0);
    expect(res.results).toHaveLength(0);
  });

  it("matches demo investigations by id and wallet", () => {
    const byName = getDemoSearchResults("phishing");
    expect(byName.total).toBeGreaterThan(0);
    expect(byName.results[0].entity_type).toBe("investigation");
    expect(byName.results[0].url).toContain("/cases/");

    const byWallet = getDemoSearchResults("0x7c5bd5c9");
    expect(byWallet.results.some((r) => r.entity_type === "investigation")).toBe(true);
  });

  it("honors the entity type filter", () => {
    const res = getDemoSearchResults("phishing", "investigation");
    expect(res.total).toBeGreaterThan(0);
    expect(res.results.every((r) => r.entity_type === "investigation")).toBe(true);
  });

  it("covers VASPs from the curated demo directory", () => {
    const res = getDemoSearchResults("binance");
    expect(res.total).toBeGreaterThan(0);
    expect(res.results[0].entity_type).toBe("vasp");
    expect(res.results[0].source).toBe("demo");
  });

  it("respects the result limit", () => {
    const res = getDemoSearchResults("0x", undefined, 2);
    expect(res.results.length).toBeLessThanOrEqual(2);
  });
});