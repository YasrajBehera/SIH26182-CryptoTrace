import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/api/assistant", () => ({
  assistant: {
    quickActions: vi.fn().mockResolvedValue([
      { id: "summarize_case", label: "Summarize the case", description: "d", scope: "case", requires_confirmation: false },
      { id: "prepare_referral", label: "Prepare a referral (draft)", description: "d", scope: "case", requires_confirmation: true },
    ]),
    query: vi.fn(),
  },
}));

import { assistant } from "@/api/assistant";
import { InvestigatorAssistant } from "./InvestigatorAssistant";
import type { AssistantResponse } from "@/api/types";

const queryMock = vi.mocked(assistant.query);

function makeResponse(overrides: Partial<AssistantResponse> = {}): AssistantResponse {
  return {
    request_id: "asr-test-1",
    intent: "summarize_case",
    title: "Case summary",
    sections: [{ heading: "Overview", body: "Grounded overview body", bullets: ["Bullet one", "Bullet two"], actions: [] }],
    evidence_ids: [],
    transaction_hashes: [],
    warnings: ["DEMO DATA — this answer is synthetic sample data, not real intelligence."],
    disclaimer: "Attribution is a transactional association, not ownership proof.",
    data_source: "demo",
    human_review_required: true,
    suggested_actions: [],
    referral_draft: null,
    ...overrides,
  };
}

describe("InvestigatorAssistant", () => {
  beforeEach(() => {
    queryMock.mockReset();
  });

  it("renders scoped quick actions and asks the assistant with one click", async () => {
    queryMock.mockResolvedValue(makeResponse());
    const user = userEvent.setup();
    render(<InvestigatorAssistant caseId="CT-2026-0142" scope="case" />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Summarize the case" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Summarize the case" }));

    await waitFor(() => expect(queryMock).toHaveBeenCalledWith({
      query: "Summarize the case",
      intent: "summarize_case",
      caseId: "CT-2026-0142",
      walletAddress: undefined,
      chain: "eth",
    }));

    expect(await screen.findByText("Grounded overview body")).toBeInTheDocument();
    expect(screen.getByText("Bullet one")).toBeInTheDocument();
    expect(screen.getByText(/transactional association/)).toBeInTheDocument();
  });

  it("requires explicit confirmation before surfacing a referral draft", async () => {
    queryMock.mockResolvedValue(
      makeResponse({
        intent: "prepare_referral",
        referral_draft: {
          title: "Draft referral — Phishing Sweep",
          case_id: "CT-2026-0142",
          primary_wallet: "0x7c5bd5c9cde06b8c998a6a66dbdc2e9e8e2f4b13",
          chain: "eth",
          summary: "Synthetic draft summarising the case.",
          evidence_ids: [],
          transaction_hashes: [],
          vasp_candidates: [],
          risk_level: "high",
          risk_score: null,
          submission_state: "requires_sahyog_connection",
          sahyog_status: "integration-ready",
        },
      }),
    );
    const user = userEvent.setup();
    render(<InvestigatorAssistant caseId="CT-2026-0142" scope="case" />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Prepare a referral (draft)" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Prepare a referral (draft)" }));

    // The confirmation dialog must appear before any draft is produced.
    expect(await screen.findByRole("button", { name: "Draft for review" })).toBeInTheDocument();
    expect(queryMock).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Draft for review" }));
    const draft = await screen.findByTestId("assistant-referral");
    expect(draft).toBeInTheDocument();
    expect(draft.textContent).toContain("never submitted autonomously");
    expect(draft.textContent).toContain("integration-ready");
    expect(queryMock).toHaveBeenCalledWith({
      query: "Prepare a referral (draft)",
      intent: "prepare_referral",
      caseId: "CT-2026-0142",
      walletAddress: undefined,
      chain: "eth",
    });
  });

  it("surfaces the error message when the query fails", async () => {
    queryMock.mockRejectedValue(new Error("The assistant could not be reached."));
    const user = userEvent.setup();
    render(<InvestigatorAssistant caseId="CT-2026-0142" scope="case" />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Summarize the case" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Summarize the case" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("The assistant could not be reached.");
  });
});