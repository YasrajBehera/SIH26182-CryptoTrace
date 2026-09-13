import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./client", () => ({ client: { get: vi.fn(), post: vi.fn() }, ApiError: class ApiError extends Error {} }));
vi.mock("./config", () => ({ isDemoMode: vi.fn() }));
vi.mock("@/mock", () => ({
  demoAssistantQuickActions: [{ id: "assist", label: "General assistance", description: "x", scope: "case", requires_confirmation: false }],
  getDemoAssistantResponse: vi.fn(),
}));

import { client } from "./client";
import { isDemoMode } from "./config";
import { getDemoAssistantResponse } from "@/mock";
import { assistant } from "./assistant";
import type { AssistantResponse } from "./types";

const getMock = vi.mocked(client.get);
const postMock = vi.mocked(client.post);
const demoMode = vi.mocked(isDemoMode);
const demoResponse = vi.mocked(getDemoAssistantResponse);

function makeResponse(overrides: Partial<AssistantResponse> = {}): AssistantResponse {
  return {
    request_id: "asr-test-1",
    intent: "summarize_case",
    title: "Case summary",
    sections: [{ heading: "Overview", body: "test body", bullets: ["b1"], actions: [] }],
    evidence_ids: [],
    transaction_hashes: [],
    warnings: [],
    disclaimer: "d",
    data_source: "live",
    human_review_required: true,
    suggested_actions: [],
    referral_draft: null,
    ...overrides,
  };
}

describe("assistant API client (live mode)", () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    demoMode.mockReset().mockReturnValue(false);
    demoResponse.mockReset();
  });

  it("posts the mapped payload to /query and returns the backend response", async () => {
    const res = makeResponse({ intent: "trace_funds" });
    postMock.mockResolvedValue(res);

    const out = await assistant.query({ query: "trace funds", caseId: "CT-1", walletAddress: "0xab", chain: "btc" });

    expect(postMock).toHaveBeenCalledWith(
      "/api/v1/assistant/query",
      {
        query: "trace funds",
        intent: undefined,
        case_id: "CT-1",
        wallet_address: "0xab",
        chain: "btc",
        wallet2: undefined,
      },
      expect.anything(),
    );
    expect(out).toEqual(res);
  });

  it("rejects malformed responses instead of serving them as data", async () => {
    postMock.mockResolvedValue({ intent: "missing_request_id" });
    await expect(assistant.query({ query: "hi" })).rejects.toThrow();
  });

  it("lists quick actions from the backend", async () => {
    getMock.mockResolvedValue([{ id: "assist", label: "General assistance", description: "x", scope: "case", requires_confirmation: false }]);
    const actions = await assistant.quickActions();
    expect(getMock).toHaveBeenCalledWith("/api/v1/assistant/quick-actions");
    expect(actions).toHaveLength(1);
  });
});

describe("assistant API client (demo mode)", () => {
  beforeEach(() => {
    demoMode.mockReset().mockReturnValue(true);
    demoResponse.mockReset();
    getMock.mockReset();
    postMock.mockReset();
  });

  it("returns the labeled synthetic response without calling the backend", async () => {
    const synth = makeResponse({ data_source: "demo", warnings: ["DEMO DATA — this answer is synthetic sample data, not real intelligence."] });
    demoResponse.mockReturnValue(synth);

    const out = await assistant.query({ query: "summarize the case", caseId: "CT-2026-0142" });

    expect(demoResponse).toHaveBeenCalledWith(
      expect.objectContaining({ query: "summarize the case", case_id: "CT-2026-0142", chain: "eth" }),
    );
    expect(postMock).not.toHaveBeenCalled();
    expect(out.data_source).toBe("demo");
  });

  it("returns demo quick actions", async () => {
    const actions = await assistant.quickActions();
    expect(actions[0].id).toBe("assist");
    expect(getMock).not.toHaveBeenCalled();
  });
});