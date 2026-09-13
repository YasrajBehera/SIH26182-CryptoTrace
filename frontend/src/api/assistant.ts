import { client, ApiError } from "./client";
import { isDemoMode } from "./config";
import { demoAssistantQuickActions, getDemoAssistantResponse } from "@/mock";
import type {
  AssistantQuickAction,
  AssistantResponse,
  BackendAssistantRequest,
} from "./types";

/**
 * M9 Investigator Intelligence Assistant (backend assistant module).
 *
 * The assistant is a deterministic, evidence-grounded query layer: it composes
 * persisted, authorized facts (cases, wallets, transactions, evidence, risk)
 * into structured answers. It never runs new analysis and never takes
 * operational action — every answer carries `human_review_required: true`.
 *
 * Live mode calls:
 *   GET  /api/v1/assistant/quick-actions
 *   POST /api/v1/assistant/query
 *
 * Demo mode returns labeled synthetic answers through the same wire shapes.
 */

export interface AssistantQueryInput {
  query: string;
  intent?: string;
  caseId?: string;
  walletAddress?: string;
  chain?: string;
  wallet2?: string;
}

function toRequest(input: AssistantQueryInput): BackendAssistantRequest {
  return {
    query: input.query,
    intent: input.intent,
    case_id: input.caseId,
    wallet_address: input.walletAddress,
    chain: input.chain ?? "eth",
    wallet2: input.wallet2,
  };
}

export const assistant = {
  async quickActions(): Promise<AssistantQuickAction[]> {
    if (isDemoMode()) return demoAssistantQuickActions;
    return client.get<AssistantQuickAction[]>("/api/v1/assistant/quick-actions");
  },

  async query(input: AssistantQueryInput): Promise<AssistantResponse> {
    if (isDemoMode()) return getDemoAssistantResponse(toRequest(input));

    const res = await client.post<AssistantResponse>(
      "/api/v1/assistant/query",
      toRequest(input),
      { timeoutMs: 45000 },
    );

    // The backend is authoritative; never let a malformed response pass as data.
    if (!res || typeof res.request_id !== "string") {
      throw new ApiError("The assistant returned an incomplete response.", {
        code: "bad_response",
        status: 502,
      });
    }
    return res;
  },
};