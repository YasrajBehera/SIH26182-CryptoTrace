import { describe, expect, it, vi } from "vitest";

vi.mock("./config", () => ({ isDemoMode: vi.fn() }));
vi.mock("./client", () => ({
  client: { get: vi.fn() },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(message: string, opts: { status?: number; code?: string } = {}) {
      super(message);
      this.status = opts.status ?? 0;
    }
  },
}));

import { isDemoMode } from "./config";
import { client, ApiError } from "./client";
import { risk } from "./risk";

const ADDR = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";

const NOT_TRAINED: Record<string, unknown> = {
  status: "not_trained",
  probability: null,
  label: "UNKNOWN",
  level: "not_assessed",
  threshold: null,
  required_features: [],
  missing_features: [],
  top_features: [],
  model_version: null,
  dataset_version: null,
  explanation: "No trained suspicious-wallet classifier artifact is available.",
  wording: "Model-estimated suspicious activity probability: UNKNOWN / NOT ASSESSED (no trained model)",
  disclaimer: "Model-estimated suspicious activity probability from a trained classifier.",
};

describe("risk.ml (live ML suspicious-wallet signal)", () => {
  it("passes the honest not_trained payload through untouched", async () => {
    vi.mocked(isDemoMode).mockReturnValue(false);
    vi.mocked(client.get).mockResolvedValue(NOT_TRAINED);
    const r = await risk.ml(ADDR);
    expect(r).not.toBeNull();
    expect(r?.status).toBe("not_trained");
    expect(r?.probability).toBeNull();
    expect(r?.wording).toContain("UNKNOWN / NOT ASSESSED");
    expect(client.get).toHaveBeenCalledWith(
      expect.stringContaining(`/api/v1/risk/wallet/${ADDR}/ml`),
      expect.anything(),
    );
  });

  it("reports unavailable (UNKNOWN) when required features are missing", async () => {
    vi.mocked(isDemoMode).mockReturnValue(false);
    vi.mocked(client.get).mockResolvedValue({
      ...NOT_TRAINED,
      status: "unavailable",
      required_features: ["tx_count", "avg_value"],
      missing_features: ["avg_value", "degree"],
      model_version: "lightgbm-0.0.0",
      dataset_version: "elliptic2-bitcoin-res-test",
    });
    const r = await risk.ml(ADDR);
    expect(r?.status).toBe("unavailable");
    expect(r?.missing_features).toContain("avg_value");
  });

  it("returns null on provider/unavailable responses (never a fake number)", async () => {
    vi.mocked(isDemoMode).mockReturnValue(false);
    vi.mocked(client.get).mockRejectedValue(new ApiError("blockchain down", { status: 502 }));
    const r = await risk.ml(ADDR);
    expect(r).toBeNull();
  });

  it("returns null in demo mode (no fabricated demo probabilities)", async () => {
    vi.mocked(isDemoMode).mockReturnValue(true);
    expect(await risk.ml(ADDR)).toBeNull();
  });
});

describe("risk.forWallet (persisted analytical risk)", () => {
  it("returns the persisted assessment when present", async () => {
    vi.mocked(isDemoMode).mockReturnValue(false);
    const assessment = { wallet_address: ADDR, chain: "eth", level: "low", risk_score: 15.5 };
    vi.mocked(client.get).mockResolvedValue(assessment);
    expect(await risk.forWallet(ADDR)).toEqual(assessment);
  });

  it("returns null on 404 (no stored assessment yet)", async () => {
    vi.mocked(isDemoMode).mockReturnValue(false);
    vi.mocked(client.get).mockRejectedValue(new ApiError("not found", { status: 404 }));
    expect(await risk.forWallet(ADDR)).toBeNull();
  });

  it("returns null in demo mode", async () => {
    vi.mocked(isDemoMode).mockReturnValue(true);
    expect(await risk.forWallet(ADDR)).toBeNull();
  });
});