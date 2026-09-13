import type { AssistantIntent, AssistantQuickAction, AssistantResponse, BackendAssistantRequest } from "@/api/types";
import { getDemoInvestigation } from "./cases";

/**
 * SYNTHETIC ASSISTANT DATA — demo only.
 *
 * The demo assistant mirrors the shape of the deterministic M9 backend module
 * (sections, warnings, data_source "demo") so the UI works without a backend,
 * but every answer is explicit synthetic material, never intelligence.
 */

export const demoAssistantQuickActions: AssistantQuickAction[] = [
  {
    id: "summarize_case",
    label: "Summarize the case",
    description: "One-paragraph overview of the case and its key facts.",
    scope: "case",
    requires_confirmation: false,
  },
  {
    id: "trace_funds",
    label: "Trace funds",
    description: "Follow the movement of funds from the primary wallet.",
    scope: "wallet",
    requires_confirmation: false,
  },
  {
    id: "find_vasp",
    label: "Find VASP / exchange",
    description: "Identify candidate service providers from persisted analysis.",
    scope: "wallet",
    requires_confirmation: false,
  },
  {
    id: "explain_attribution",
    label: "Explain attribution",
    description: "Why the current VASP candidates were surfaced. Not ownership proof.",
    scope: "case",
    requires_confirmation: false,
  },
  {
    id: "suspicious_transactions",
    label: "Review suspicious transactions",
    description: "Flag unusual transfers from stored transaction data.",
    scope: "wallet",
    requires_confirmation: false,
  },
  {
    id: "build_timeline",
    label: "Build timeline",
    description: "Chronological sequence of stored transfers and evidence.",
    scope: "wallet",
    requires_confirmation: false,
  },
  {
    id: "explain_risk",
    label: "Explain risk score",
    description: "Break the persisted risk assessment down by factor.",
    scope: "case",
    requires_confirmation: false,
  },
  {
    id: "generate_report",
    label: "Generate report outline",
    description: "Assemble the report structure for the case.",
    scope: "case",
    requires_confirmation: false,
  },
  {
    id: "prepare_referral",
    label: "Prepare a referral (draft)",
    description: "Assemble a draft lawful referral for investigator review.",
    scope: "case",
    requires_confirmation: true,
  },
  {
    id: "compare_wallets",
    label: "Compare two wallets",
    description: "Side-by-side activity, risk and evidence for two addresses.",
    scope: "wallet",
    requires_confirmation: false,
  },
  {
    id: "what_changed",
    label: "What changed since last update",
    description: "Deltas between the stored case snapshot and current stores.",
    scope: "case",
    requires_confirmation: false,
  },
  {
    id: "assist",
    label: "General assistance",
    description: "Ask anything about a wallet or case in natural language.",
    scope: "case",
    requires_confirmation: false,
  },
];

const DISCLAIMER =
  "These observations are generated from persisted case, wallet and evidence data. Attribution is a transactional association, not ownership proof. Nothing here is enforcement action; an investigator must review all reasoning before acting.";

const DEMO_WARNING = "DEMO DATA — this answer is synthetic sample data, not real intelligence.";

/** Resolve the most specific intents first, mirroring the backend ranking. */
function detectIntent(query: string): AssistantIntent {
  const groups: Array<[AssistantIntent, string[]]> = [
    ["prepare_referral", ["referral", "disclosure", "sahyog", "lawful", "lodr", "submit", "移交", "报案", "司法"]],
    ["what_changed", ["changed", "what changed", "since last", "diff", "delta", "变化", "更新", "差异"]],
    ["compare_wallets", ["compare", "comparison", "versus", "vs", "two wallets", "对比", "比较", "两个钱包"]],
    ["explain_risk", ["risk", "score", "level", "threat", "exposure", "风险", "评分", "等级"]],
    ["explain_attribution", ["why", "explain", "reasoning", "justify", "based on", "为什么", "解释", "依据", "理由"]],
    ["suspicious_transactions", ["suspicious", "malicious", "large", "flag", "anomal", "wash", "fraud", "异常", "可疑", "洗钱", "大额"]],
    ["trace_funds", ["trace", "track", "follow", "flow", "path", "hop", "追踪", "流向", "路径", "资金"]],
    ["find_vasp", ["vasp", "exchange", "attribution", "identify", "candidate", "交易所", "归属", "识别", "平台"]],
    ["build_timeline", ["timeline", "chronolog", "history", "sequence", "时间线", "时间轴", "历史"]],
    ["generate_report", ["report", "pdf", "export", "document", "报告", "导出", "文档"]],
    ["summarize_case", ["summary", "summarize", "overview", "status", "brief", "总结", "简介", "摘要", "概述", "状态"]],
  ];
  const text = query.toLowerCase();
  for (const [intent, keys] of groups) {
    if (keys.some((k) => text.includes(k))) return intent;
  }
  return "assist";
}

export function getDemoAssistantResponse(payload: BackendAssistantRequest): AssistantResponse {
  const intent = (payload.intent as AssistantIntent | undefined) ?? detectIntent(payload.query ?? "");
  const address = payload.wallet_address ?? "";
  const caseId = payload.case_id ?? "";
  const demoCase = caseId ? getDemoInvestigation(caseId) : undefined;
  const focus = demoCase?.name ?? (address ? `${address.slice(0, 6)}…${address.slice(-4)}` : "this entity");

  const bullets: string[] = [];
  if (demoCase) {
    bullets.push(`Case ${demoCase.id} “${demoCase.name}” — status ${demoCase.status}, risk ${demoCase.risk}.`);
    bullets.push(`Primary wallet ${demoCase.primaryWallet.slice(0, 6)}…${demoCase.primaryWallet.slice(-4)} (${demoCase.network}).`);
    bullets.push(`Persisted totals: ${demoCase.transactions} transactions, ${demoCase.vaspCandidates} VASP candidates, ${demoCase.evidenceCount} evidence items.`);
  } else if (address) {
    bullets.push(`No persisted case references ${address.slice(0, 6)}…${address.slice(-4)} in the demo dataset.`);
    bullets.push(`Wallet-scoped observations are limited to what is stored for the address.`);
  } else {
    bullets.push(`No case id or wallet address was provided, so observations are limited to the demo dataset itself.`);
  }

  return {
    request_id: `asr-demo-${Date.now()}`,
    intent,
    title: titleFor(intent, focus),
    sections: [
      {
        heading: "Overview",
        body: `Demo assistant response for ${focus}.`,
        bullets,
        actions: [],
      },
      {
        heading: "Observations",
        body:
          "In the mock adapter the assistant reflects the labeled synthetic case/echelon facts only; it never invents transactions, VASP identities or timestamps.",
        bullets: [
          demoCase ? `Risk level recorded as ${demoCase.risk}.` : "No persisted risk summary is available for this scope.",
          intent === "trace_funds" ? "A synthetic hop chain is available in the graph demo." : "Graph traversal is exercised in the graph demo.",
        ],
        actions: [],
      },
    ],
    evidence_ids: demoCase ? [`ev-demo-${demoCase.id.toLowerCase()}`] : [],
    transaction_hashes: [],
    warnings: [DEMO_WARNING],
    disclaimer: DISCLAIMER,
    data_source: "demo",
    human_review_required: true,
    suggested_actions: demoAssistantQuickActions.slice(0, 4),
    referral_draft:
      intent === "prepare_referral" && demoCase
        ? {
            title: `Draft referral — ${demoCase.name}`,
            case_id: demoCase.id,
            primary_wallet: demoCase.primaryWallet,
            chain: "eth",
            summary: `Synthetic draft summarising case ${demoCase.id} for investigator review.`,
            evidence_ids: [],
            transaction_hashes: [],
            vasp_candidates: demoCase.vaspCandidates ? [`demo-candidate-${demoCase.id.toLowerCase()}`] : [],
            risk_level: demoCase.risk,
            risk_score: null,
            submission_state: "requires_sahyog_connection",
            sahyog_status: "integration-ready",
          }
        : null,
  };
}

function titleFor(intent: AssistantIntent, focus: string): string {
  const titles: Record<AssistantIntent, string> = {
    summarize_case: "Case summary",
    trace_funds: "Fund movement trace",
    find_vasp: "VASP / exchange candidates",
    explain_attribution: "Attribution reasoning",
    suspicious_transactions: "Suspicious transaction review",
    build_timeline: "Activity timeline",
    explain_risk: "Risk score breakdown",
    generate_report: "Report outline",
    prepare_referral: "Referral draft (for review)",
    compare_wallets: "Wallet comparison",
    what_changed: "Changes since last update",
    assist: `Notes on ${focus}`,
  };
  return titles[intent];
}