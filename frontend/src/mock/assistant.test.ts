import { describe, expect, it } from "vitest";
import { demoAssistantQuickActions, getDemoAssistantResponse } from "./assistant";
import type { BackendAssistantRequest } from "@/api/types";

function request(overrides: Partial<BackendAssistantRequest> = {}): BackendAssistantRequest {
  return { query: "summarize the case", chain: "eth", ...overrides };
}

describe("demo assistant quick actions", () => {
  it("mirrors the backend intent set", () => {
    const ids = demoAssistantQuickActions.map((a) => a.id);
    expect(ids).toEqual([
      "summarize_case",
      "trace_funds",
      "find_vasp",
      "explain_attribution",
      "suspicious_transactions",
      "build_timeline",
      "explain_risk",
      "generate_report",
      "prepare_referral",
      "compare_wallets",
      "what_changed",
      "assist",
    ]);
  });

  it("marks the referral action as requiring confirmation", () => {
    const referral = demoAssistantQuickActions.find((a) => a.id === "prepare_referral");
    expect(referral?.requires_confirmation).toBe(true);
  });
});

describe("demo assistant response intent detection", () => {
  const cases: Array<[string, string]> = [
    ["summarize the case", "summarize_case"],
    ["explain the risk score please", "explain_risk"],
    ["trace funds from this wallet", "trace_funds"],
    ["is anything suspicious here", "suspicious_transactions"],
    ["compare these two wallets", "compare_wallets"],
    ["what changed since last update", "what_changed"],
    ["prepare a referral", "prepare_referral"],
    ["what happened on this timeline", "build_timeline"],
  ];

  cases.forEach(([q, intent]) => {
    it(`maps "${q}" to ${intent}`, () => {
      expect(getDemoAssistantResponse(request({ query: q })).intent).toBe(intent);
    });
  });
});

describe("demo assistant response grounding", () => {
  it("labels the answer as synthetic demo data", () => {
    const res = getDemoAssistantResponse(request());
    expect(res.data_source).toBe("demo");
    expect(res.human_review_required).toBe(true);
    expect(res.warnings.some((w) => w.includes("synthetic"))).toBe(true);
    expect(res.request_id.startsWith("asr-demo-")).toBe(true);
  });

  it("grounds a case-aware summary in the labeled demo case", () => {
    const res = getDemoAssistantResponse(request({ case_id: "CT-2026-0142" }));
    const body = res.sections.map((s) => `${s.body ?? ""} ${s.bullets.join(" ")}`).join(" ");
    expect(body).toContain("CT-2026-0142");
    expect(body).toContain("Phishing Sweep");
    expect(res.evidence_ids).toContain("ev-demo-ct-2026-0142");
  });

  it("produces a draft-only referral with an explicit non-submission state", () => {
    const res = getDemoAssistantResponse(request({ query: "prepare a referral", case_id: "CT-2026-0142" }));
    expect(res.referral_draft).not.toBeNull();
    expect(res.referral_draft?.submission_state).toBe("requires_sahyog_connection");
    expect(res.referral_draft?.sahyog_status).toBe("integration-ready");
    expect(res.referral_draft?.case_id).toBe("CT-2026-0142");
  });

  it("does not invent a referral when the case is unknown", () => {
    const res = getDemoAssistantResponse(request({ query: "prepare a referral", case_id: "CT-9999" }));
    expect(res.referral_draft).toBeNull();
  });
});