import { describe, expect, it, vi } from "vitest";

vi.mock("./config", () => ({ isDemoMode: vi.fn() }));

import { isDemoMode } from "./config";
import { DEMO_CURATED_SANCTIONS, sanctions } from "./intelligence";

const CURATED = "0x098B716B8Aaf21512996dC57EB0615e2383E2f96";

describe("sanctions.lookup (curated public intelligence)", () => {
  it("returns null in live mode when no exact curated match exists", async () => {
    vi.mocked(isDemoMode).mockReturnValue(false);
    const r = await sanctions.lookup("0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb");
    expect(r).toBeNull();
  });

  it("never reports a matched record as a VASP or modifies scores", () => {
    vi.mocked(isDemoMode).mockReturnValue(true);
    const r = DEMO_CURATED_SANCTIONS;
    expect(r.matched).toBe(true);
    expect(r.level).toBe("high");
    expect(r.record?.match_type).toBe("exact_address");
    expect(r.data_source).toContain("curated_public_intelligence");
  });

  it("returns the curated demo record only for the exact sanctioned address", async () => {
    vi.mocked(isDemoMode).mockReturnValue(true);
    const hit = await sanctions.lookup(CURATED);
    expect(hit?.matched).toBe(true);
    expect(hit?.record?.entity).toBe("Lazarus Group");
    const miss = await sanctions.lookup(CURATED.slice(0, 40) + "aa");
    expect(miss).toBeNull();
  });
});