"""M9 Investigator Intelligence Assistant: deterministic answer composition.

The assistant maps an intent (quick action id or free-form keywords) to a set
of grounded, read-only tool calls against the persisted investigation data
stores, then renders the results as structured sections plus evidence ids,
transaction hashes, warnings and the data-source policy. Nothing is invented;
every statement either comes from stored data or is an explicit
"unavailable / not yet analyzed" note.
"""

from __future__ import annotations

import re
import uuid
from collections import Counter
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from app.audit.service import AuditService, get_audit_service
from assistant.models import (
    AssistantQuickAction,
    AssistantRequest,
    AssistantResponse,
    AssistantSection,
    ReferralDraft,
)
from assistant.tools import AssistantTools, extract_addresses, iso_utc

MAX_BULLETS = 25
_MAX_TIMELINE_EVENTS = 25

DISCLAIMER = (
    "CryptoTrace AI Investigator output is generated deterministically from "
    "stored evidence. It is investigative support — not a determination of "
    "criminality, illegality, or ownership. Every answer must be reviewed by "
    "a human investigator before any operational action."
)

DEMO_WARNING = "This answer reflects DEMO/SYNTHETIC data. Do not rely on it for operational decisions."
MIXED_WARNING = "This answer mixes real chain events with synthetic demo records. Separate them before use."
UNAVAILABLE_WARNING = "No corroborated live data was available for part of this answer; gaps are marked UNAVAILABLE."
GRAPH_WARNING = "Deep graph traversal (Neo4j) is unavailable for this query; hop results come from stored transactions only."
REFERRAL_WARNING = "Draft referral only. Requires investigator review. No submission is made; live submission needs an authorized SAHYOG connection."
SUSPICIOUS_WARNING = "References are heuristic flags for review, not declarations of criminality."

QUICK_ACTIONS: List[AssistantQuickAction] = [
    AssistantQuickAction(
        id="summarize_case",
        label="Summarize this case",
        description="Overview of the case, latest analysis, attribution and risk.",
        scope="case",
    ),
    AssistantQuickAction(
        id="trace_funds",
        label="Trace funds",
        description="Follow flow into/out of a wallet and find hop paths.",
        scope="wallet",
    ),
    AssistantQuickAction(
        id="find_vasp",
        label="Find VASP candidates",
        description="Surface stored attribution candidates for a wallet.",
        scope="wallet",
    ),
    AssistantQuickAction(
        id="explain_attribution",
        label="Explain attribution",
        description="Why the top VASP candidate ranks highest and its evidence.",
        scope="wallet",
    ),
    AssistantQuickAction(
        id="suspicious_transactions",
        label="Flag suspicious transactions",
        description="Heuristic review flags for large or repeated flows.",
        scope="wallet",
    ),
    AssistantQuickAction(
        id="build_timeline",
        label="Build a timeline",
        description="Chronological events: transfers and recorded evidence.",
        scope="wallet",
    ),
    AssistantQuickAction(
        id="explain_risk",
        label="Explain the risk score",
        description="How the analytical risk level and score were derived.",
        scope="wallet",
    ),
    AssistantQuickAction(
        id="explain_sanctions",
        label="Why is this wallet high risk?",
        description="Criminal/sanctions intelligence from the curated public sanctions/illicit record set.",
        scope="wallet",
    ),
    AssistantQuickAction(
        id="generate_report",
        label="Generate a report",
        description="Reference report sections/ids generated for the case.",
        scope="case",
    ),
    AssistantQuickAction(
        id="prepare_referral",
        label="Prepare a referral (draft)",
        description="Assemble a draft lawful referral for investigator review.",
        scope="case",
        requires_confirmation=True,
    ),
    AssistantQuickAction(
        id="compare_wallets",
        label="Compare two wallets",
        description="Side-by-side activity, risk and evidence for two addresses.",
        scope="wallet",
    ),
    AssistantQuickAction(
        id="what_changed",
        label="What changed since last update",
        description="Deltas between the stored case snapshot and current stores.",
        scope="case",
    ),
    AssistantQuickAction(
        id="assist",
        label="General assistance",
        description="Ask anything about a wallet or case in natural language.",
        scope="wallet",
    ),
]

_INTENT_NAMES = {action.id for action in QUICK_ACTIONS}

# Keyword groups: (english tokens, chinese tokens). Order matters: earlier
# intent groups are matched first when a query contains several keywords.
_INTENT_KEYWORDS: List[Tuple[str, List[str], List[str]]] = [
    ("prepare_referral", ["referral", "disclosure", "sahyog", "lawful", "lodr", "submit"], ["移交", "报案", "司法", "披露"]),
    ("what_changed", ["changed", "what changed", "since last", "diff", "delta"], ["变化", "更新", "差异"]),
    ("compare_wallets", ["compare", "comparison", "versus", "vs", "two wallets"], ["对比", "比较", "两个钱包"]),
    ("explain_sanctions", ["sanctions", "sanctioned", "criminal", "illicit", "lazarus", "ofac", "why is this wallet high risk", "why is this high risk"], ["制裁", "犯罪", "非法", "高风险"]),
    ("explain_risk", ["risk", "score", "level", "threat", "exposure"], ["风险", "评分", "等级"]),
    ("explain_attribution", ["why", "explain", "reasoning", "justify", "based on"], ["为什么", "解释", "依据", "理由"]),
    ("suspicious_transactions", ["suspicious", "malicious", "large", "flag", "anomal", "wash", "fraud"], ["异常", "可疑", "洗钱", "诈骗", "大额"]),
    ("trace_funds", ["trace", "track", "follow", "flow", "path", "where", "move", "hop"], ["追踪", "流向", "路径", "流向哪里", "资金"]),
    ("find_vasp", ["vasp", "exchange", "attribution", "identify", "platform", "candidate"], ["vasp", "交易所", "归属", "识别", "平台"]),
    ("build_timeline", ["timeline", "chronolog", "history", "sequence"], ["时间线", "时间轴", "历史", "顺序"]),
    ("generate_report", ["report", "pdf", "export", "document"], ["报告", "导出", "文档"]),
    ("summarize_case", ["summary", "summarize", "overview", "status", "update", "brief"], ["总结", "简介", "摘要", "概述", "状态", "进展"]),
]

_WALLET_RE = re.compile(r"0x[a-fA-F0-9]{40}")


def _safe_decimal(value) -> Decimal:
    try:
        return Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError):
        return Decimal(0)


def _num(value) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def _asset(row: dict, chain: str) -> str:
    symbol = row.get("token_symbol")
    if symbol:
        return symbol
    return {"bsc": "BNB"}.get(chain, chain.upper())


class AssistantService:
    def __init__(
        self,
        tools: Optional[AssistantTools] = None,
        audit: Optional[AuditService] = None,
    ) -> None:
        self.tools = tools or AssistantTools()
        self.audit = audit or get_audit_service()

    # ------------------------------------------------------------------ #
    # Public surface
    # ------------------------------------------------------------------ #
    def quick_actions(self) -> List[AssistantQuickAction]:
        return QUICK_ACTIONS

    def interact(
        self,
        request: AssistantRequest,
        user,
    ) -> AssistantResponse:
        request_id = f"asr-{uuid.uuid4().hex[:12]}"
        self._graph_available: Optional[bool] = None

        case_id = request.case_id
        wallet_address = (request.wallet_address or "").strip().lower()

        extracted = extract_addresses(request.query)
        if not wallet_address and extracted:
            wallet_address = extracted[0].lower()
        wallet2 = (request.wallet2 or "").strip().lower()
        if not wallet2 and len(extracted) > 1:
            wallet2 = extracted[1].lower()

        intent = self._resolve_intent(request, wallet_address)
        title = self._title_for(intent, case_id, wallet_address)

        ctx = None
        record: Optional[dict] = None
        if case_id:
            ctx = self.tools.get_case(case_id, user)
            record = self.tools.get_case_record(case_id, user)

        sections: List[AssistantSection] = []
        if intent in {"summarize_case", "generate_report", "prepare_referral",
                      "what_changed"} and case_id:
            sections = self._answer_case_intent(intent, ctx, record)
        elif intent == "trace_funds" and (wallet_address or case_id):
            sections = self._answer_trace_funds(
                request, ctx, wallet_address, wallet2, user
            )
        elif intent in {"find_vasp", "explain_attribution",
                        "suspicious_transactions", "build_timeline",
                        "explain_risk", "explain_sanctions", "assist"} and (wallet_address or case_id):
            sections = self._answer_wallet_intent(
                intent, request, ctx, record, case_id, wallet_address, user
            )
        elif intent == "compare_wallets":
            sections = self._answer_compare_wallets(
                request, ctx, wallet_address, wallet2, user
            )
        else:
            sections = self._answer_no_scope()

        evidence, tx_hashes, data_source = self._collect_runtime(
            intent, case_id, ctx, record, wallet_address, user
        )
        warnings = self._warnings_for(data_source, intent)

        response = AssistantResponse(
            request_id=request_id,
            intent=intent,
            title=title,
            sections=sections,
            evidence_ids=evidence,
            transaction_hashes=tx_hashes,
            warnings=warnings,
            disclaimer=DISCLAIMER,
            data_source=data_source,
            human_review_required=True,
            suggested_actions=self._suggested_actions(case_id, wallet_address),
        )

        if intent == "prepare_referral" and case_id:
            response.referral_draft = self._build_referral_draft(ctx, record)

        self.audit.record_event(
            user=user.username,
            action="ASSISTANT_QUERY",
            resource=case_id or wallet_address or "no-scope",
            resource_id=request_id,
            result=f"{intent}:{data_source}",
        )
        return response

    # ------------------------------------------------------------------ #
    # Intent resolution
    # ------------------------------------------------------------------ #
    def _resolve_intent(self, request: AssistantRequest, wallet_address: str) -> str:
        hint = (request.intent or "").strip().lower()
        if hint in _INTENT_NAMES:
            return hint
        text = f"{request.query} {wallet_address}".lower()
        for intent, en, zh in _INTENT_KEYWORDS:
            if any(tok in text for tok in en) or any(tok in text for tok in zh):
                return intent
        return "assist"

    @staticmethod
    def _title_for(
        intent: str, case_id: Optional[str], wallet_address: Optional[str]
    ) -> str:
        scope = f"case {case_id}" if case_id else (
            f"wallet {wallet_address}" if wallet_address else "workspace"
        )
        titles = {
            "summarize_case": f"Case summary ({scope})",
            "trace_funds": f"Fund tracing ({scope})",
            "find_vasp": f"VASP candidates ({scope})",
            "explain_attribution": f"Attribution explanation ({scope})",
            "suspicious_transactions": f"Suspicious transaction review ({scope})",
            "build_timeline": f"Chronological timeline ({scope})",
            "explain_risk": f"Risk explanation ({scope})",
            "explain_sanctions": f"Criminal / sanctions intelligence ({scope})",
            "generate_report": f"Report references ({scope})",
            "prepare_referral": f"Draft referral ({scope})",
            "compare_wallets": "Wallet comparison",
            "what_changed": f"Changes since last update ({scope})",
            "assist": f"Investigator intelligence ({scope})",
        }
        return titles.get(intent, "Investigator intelligence")

    # ------------------------------------------------------------------ #
    # Case-scoped answers
    # ------------------------------------------------------------------ #
    def _answer_case_intent(
        self, intent: str, ctx, record: Optional[dict]
    ) -> List[AssistantSection]:
        if intent == "summarize_case":
            return self._summarize_case(ctx, record)
        if intent == "generate_report":
            return self._report_references(ctx)
        if intent == "prepare_referral":
            return self._referral_narrative(ctx, record)
        return self._what_changed(ctx)

    def _summarize_case(
        self, ctx, record: Optional[dict]
    ) -> List[AssistantSection]:
        case = ctx.case
        overview_bullets = [
            f"Status: {case.status} · Priority: {case.priority}",
            f"Risk: {case.risk or 'unknown'}",
            f"Primary wallet: {case.primary_wallet} ({case.network})",
            f"Transactions stored: {case.transactions}",
            f"VASP candidates recorded: {case.vasp_candidates}",
            f"Evidence records: {case.evidence_count}",
            f"Assigned analyst: {case.assigned_analyst}",
            f"Created {case.created_at} · Updated {case.updated_at}",
        ]
        if case.description:
            overview_bullets.append(f"Description: {case.description[:300]}")

        sections = [
            AssistantSection(heading="Case overview", bullets=overview_bullets)
        ]

        latest = ctx.latest_analysis
        if latest:
            sections.append(
                AssistantSection(
                    heading="Latest analysis",
                    bullets=[
                        f"Analysis id: {latest['analysis_id']}",
                        f"Data source: {latest.get('data_source') or 'unavailable'}",
                        f"Candidates: {latest.get('candidate_count') or 0}",
                        f"Transactions: {latest.get('transaction_count') or 0}",
                    ],
                )
            )
        else:
            sections.append(
                AssistantSection(
                    heading="Latest analysis",
                    bullets=["No analysis has been applied to this case yet."],
                )
            )

        sections.extend(self._attribution_section(record))
        sections.extend(self._risk_section(ctx))

        if ctx.wallet_summary:
            summary = ctx.wallet_summary
            sections.append(
                AssistantSection(
                    heading="Wallet activity",
                    bullets=[
                        f"First seen: {summary.get('first_seen') or 'UNAVAILABLE'}",
                        f"Last activity: {summary.get('last_activity') or 'UNAVAILABLE'}",
                        f"Balance: {summary.get('balance') or 'UNAVAILABLE'}",
                    ],
                )
            )
        return sections

    def _attribution_section(self, record: Optional[dict]) -> List[AssistantSection]:
        candidates = self.tools.get_case_candidates(record) if record else []
        if not candidates:
            return [
                AssistantSection(
                    heading="Attribution",
                    bullets=["No stored VASP candidates for this case."],
                )
            ]
        bullets = []
        for candidate in candidates[:MAX_BULLETS]:
            name = candidate.get("vasp_name", "UNKNOWN")
            score = candidate.get("score", 0)
            confidence = candidate.get("confidence", "LOW")
            bullets.append(
                f"{name} — score {score:.2f}/100, confidence {confidence}"
            )
        top = candidates[0]
        top_bullets = ["Attribution reflects transactional association only — never ownership."]
        for expl in (top.get("explanation") or [])[:3]:
            top_bullets.append(f"- {expl}")
        top_bullets.append(
            f"Evidence ids: {', '.join(top.get('evidence_ids') or []) or 'none'}"
        )
        return [
            AssistantSection(heading="Attribution candidates", bullets=bullets),
            AssistantSection(
                heading=f"Why {top.get('vasp_name', 'UNKNOWN')} ranks highest",
                bullets=top_bullets,
            ),
        ]

    def _risk_section(self, ctx) -> List[AssistantSection]:
        risk = ctx.risk
        if risk is None:
            return [
                AssistantSection(
                    heading="Risk",
                    bullets=["No analytical risk assessment recorded yet."],
                )
            ]
        bullets = [
            f"Level: {risk.level} · Score: {risk.risk_score:.0f}/100",
            f"Summary: {risk.summary}",
        ]
        bullets.extend(f"- {line}" for line in risk.reasoning[:8])
        sections = [AssistantSection(heading="Analytical risk", bullets=bullets)]
        if risk.criminal_intelligence:
            ci = risk.criminal_intelligence
            sections.append(
                AssistantSection(
                    heading="Criminal / Sanctions Intelligence (separate)",
                    bullets=[
                        f"Level: {ci.get('level')} · Entity: {ci.get('entity')} "
                        f"· Source: {ci.get('source')} · Confidence: "
                        f"{ci.get('confidence')}",
                        f"Match type: {ci.get('match_type')} · Evidence id: "
                        f"{ci.get('evidence_id') or 'UNAVAILABLE'}",
                        "Source: curated public intelligence (not a live OFAC "
                        "integration). Verify independently.",
                    ],
                )
            )
        return sections

    def _report_references(self, ctx) -> List[AssistantSection]:
        if not ctx.reports:
            return [
                AssistantSection(
                    heading="Reports",
                    body="No report has been generated for this case yet.",
                    bullets=[
                        "Use the Reports workspace to generate a PDF before export.",
                    ],
                )
            ]
        return [
            AssistantSection(
                heading="Generated reports",
                bullets=[f"Report id: {rid}" for rid in ctx.reports],
            )
        ]

    def _referral_narrative(
        self, ctx, record: Optional[dict]
    ) -> List[AssistantSection]:
        case = ctx.case
        bullets = [
            f"Case: {case.name} ({case.id})",
            f"Primary wallet: {case.primary_wallet} · Network: {case.network}",
            f"Risk: {case.risk or 'unknown'}",
            f"Evidence records available: {case.evidence_count}",
            f"Transactions stored: {case.transactions}",
        ]
        top = (self.tools.get_case_candidates(record) or [{}])[0]
        if top.get("vasp_name"):
            bullets.append(
                f"Top association candidate: {top.get('vasp_name')} "
                f"({top.get('score', 0):.2f}/100)"
            )
        return [
            AssistantSection(
                heading="Draft referral narrative",
                body=(
                    "This draft is assembled from persisted case data for the "
                    "investigator to review and refine. No submission is made."
                ),
                bullets=bullets,
            ),
            AssistantSection(
                heading="What to include before referral",
                bullets=[
                    "Attach all evidence ids referenced by this response.",
                    "Confirm the data source (live vs demo) for each attachment.",
                    "Complete the SAHYOG complaint/disclosure form manually.",
                    "Obtain supervisor approval before any external submission.",
                ],
            ),
        ]

    def _what_changed(self, ctx) -> List[AssistantSection]:
        case = ctx.case
        changes: List[str] = []

        current_evidence = self.tools.get_evidence_for_investigation(case.id, None)
        delta_evidence = len(current_evidence) - case.evidence_count
        if delta_evidence > 0:
            changes.append(
                f"{delta_evidence} new evidence record(s) exist beyond the "
                "stored case snapshot (run 'Apply analysis' to sync the case)."
            )
        elif delta_evidence < 0:
            changes.append(
                f"{abs(delta_evidence)} evidence record(s) were removed from "
                "the store since the case snapshot."
            )

        risk = ctx.risk
        if risk is not None and case.risk != risk.level:
            changes.append(
                f"Risk moved from {case.risk or 'unknown'} to {risk.level} "
                f"({risk.risk_score:.0f}/100)."
            )

        stored_tx = self.tools.wallets.repository.list_transactions(
            address=case.primary_wallet, chain=case.network, limit=500
        )
        if len(stored_tx) > case.transactions:
            changes.append(
                f"{len(stored_tx) - case.transactions} new transfer(s) stored "
                "since the case snapshot."
            )
        elif len(stored_tx) < case.transactions:
            changes.append(
                f"{case.transactions - len(stored_tx)} stored transfer(s) are "
                "no longer present in the wallet store."
            )

        if not changes:
            changes.append(
                "No changes detected since the last recorded update of this case."
            )
        return [AssistantSection(heading="Change summary", bullets=changes)]

    # ------------------------------------------------------------------ #
    # Wallet-scoped answers
    # ------------------------------------------------------------------ #
    def _answer_wallet_intent(
        self,
        intent: str,
        request: AssistantRequest,
        ctx,
        record: Optional[dict],
        case_id: Optional[str],
        wallet_address: Optional[str],
        user,
    ) -> List[AssistantSection]:
        if ctx is not None:
            chain = ctx.case.network
            address = ctx.case.primary_wallet
        else:
            chain = request.chain
            address = wallet_address

        transfers = self.tools.get_transactions(address, chain, user) or []
        evidence = (
            self.tools.get_evidence_for_investigation(case_id, user)
            if case_id
            else self.tools.get_evidence(address, chain, user)
        )
        risk = (
            ctx.risk
            if ctx is not None and ctx.risk is not None
            else self.tools.get_risk(address, chain, user)
        )

        if intent == "find_vasp":
            return self._find_vasp(ctx, record, address, chain, evidence)
        if intent == "explain_attribution":
            return self._explain_attribution(ctx, record, address, chain, evidence)
        if intent == "suspicious_transactions":
            return self._suspicious_transactions(address, chain, transfers)
        if intent == "build_timeline":
            return self._build_timeline(address, chain, transfers, evidence)
        if intent == "explain_risk":
            return self._explain_risk(address, chain, risk)
        if intent == "explain_sanctions":
            return self._answer_sanctions_intelligence(address, chain, evidence, risk)
        return self._assist_wallet(address, chain, transfers, evidence, risk)

    def _find_vasp(
        self,
        ctx,
        record: Optional[dict],
        address: str,
        chain: str,
        evidence,
    ) -> List[AssistantSection]:
        if ctx is not None:
            return self._attribution_section(record)
        if not evidence:
            return [
                AssistantSection(
                    heading="VASP candidates",
                    body=(
                        "No stored attribution evidence for this wallet yet. "
                        "Run an analysis on the wallet first."
                    ),
                    bullets=["UNAVAILABLE — no candidate data to report yet."],
                )
            ]
        by_analysis: Dict[str, List] = {}
        for rec in evidence:
            by_analysis.setdefault(rec.attribution_id, []).append(rec)
        bullets = []
        for analysis_id, records in list(by_analysis.items())[:5]:
            top_conf = max((r.confidence for r in records), default=0.0)
            bullets.append(
                f"Attribution set {analysis_id}: {len(records)} evidence "
                f"records, top confidence {top_conf:.2f} (transactional "
                "association signal only)."
            )
        return [
            AssistantSection(
                heading="VASP candidates (from stored evidence)",
                bullets=bullets,
            )
        ]

    def _explain_attribution(
        self,
        ctx,
        record: Optional[dict],
        address: str,
        chain: str,
        evidence,
    ) -> List[AssistantSection]:
        if ctx is not None and ctx.case.vasp_candidates:
            return self._attribution_section(record)
        if not evidence:
            return [
                AssistantSection(
                    heading="Attribution explanation",
                    bullets=["No stored attribution evidence to explain yet."],
                )
            ]
        bullets = []
        for rec in evidence[:MAX_BULLETS]:
            bullets.append(
                f"[{rec.evidence_type.value}] source={rec.source} "
                f"confidence={rec.confidence:.2f} — "
                f"{(rec.description or '')[:180]}"
            )
        top = max(evidence, key=lambda r: r.confidence, default=None)
        if top is not None:
            bullets.insert(
                0,
                f"Strongest signal: {top.evidence_type.value} "
                f"(confidence {top.confidence:.2f}, source {top.source}).",
            )
        return [
            AssistantSection(
                heading="Why this attribution signal ranks highest",
                body=(
                    "Candidate explanations come from the attribution engine's "
                    "recorded evidence — transactional association only."
                ),
                bullets=bullets,
            )
        ]

    def _suspicious_transactions(
        self, address, chain, transfers
    ) -> List[AssistantSection]:
        if not transfers:
            return [
                AssistantSection(
                    heading="Suspicious transaction review",
                    bullets=["No stored transactions for this wallet to review."],
                )
            ]

        inbound = [t for t in transfers if (t.get("to_address") or "").lower() == address.lower()]
        outbound = [t for t in transfers if (t.get("from_address") or "").lower() == address.lower()]
        counterparties = Counter(
            (t.get("to_address") or "").lower()
            if (t.get("from_address") or "").lower() == address.lower()
            else (t.get("from_address") or "").lower()
            for t in transfers
        )
        totals = {"in": _safe_decimal(0), "out": _safe_decimal(0)}
        for t in transfers:
            value = _safe_decimal(t.get("value"))
            if (t.get("to_address") or "").lower() == address.lower():
                totals["in"] += value
            elif (t.get("from_address") or "").lower() == address.lower():
                totals["out"] += value

        by_value = sorted(transfers, key=_num, reverse=True)
        bullets = [
            f"Stored transactions: {len(transfers)} "
            f"({len(inbound)} inbound / {len(outbound)} outbound).",
            f"Aggregate value: in {totals['in']} / out {totals['out']}.",
        ]
        flags = []
        for t in by_value[:5]:
            direction = "in" if (t.get("to_address") or "").lower() == address.lower() else "out"
            flag = (
                f"{direction.upper()} {t.get('value')} "
                f"{_asset(t, chain)} on "
                f"{iso_utc(t.get('block_timestamp')) or 'UNAVAILABLE'} "
                f"({t.get('tx_hash')})"
            )
            flags.append(flag)
        repeated = [f"{cp} ({count} tx)" for cp, count in counterparties.most_common(5) if count >= 3]
        if flags:
            bullets.append("Largest recorded flows:")
            bullets.extend(f"- {f}" for f in flags)
        if repeated:
            bullets.append("Counterparties appearing in 3+ transactions (review):")
            bullets.extend(f"- {r}" for r in repeated)
        else:
            bullets.append(
                "No counterparty appears in 3 or more stored transactions."
            )
        return [
            AssistantSection(
                heading="Suspicious transaction review",
                body=(
                    f"Wallet {address} on {chain}. Flags are heuristic and must "
                    "be reviewed by an investigator."
                ),
                bullets=bullets,
            )
        ]

    def _build_timeline(
        self, address, chain, transfers, evidence
    ) -> List[AssistantSection]:
        events: List[Tuple[int, str]] = []
        for t in transfers:
            ts = t.get("block_timestamp")
            try:
                key = int(ts) if ts is not None else 0
            except (TypeError, ValueError):
                key = 0
            direction = "in" if (t.get("to_address") or "").lower() == address.lower() else "out"
            events.append(
                (
                    key,
                    f"{iso_utc(ts) or 'UNAVAILABLE'} · {direction.upper()} "
                    f"{t.get('value')} {_asset(t, chain)} "
                    f"({t.get('tx_hash')})",
                )
            )
        for rec in evidence:
            key = 0
            if rec.timestamp is not None:
                try:
                    key = int(rec.timestamp)
                except (TypeError, ValueError):
                    key = 0
            events.append(
                (
                    key,
                    f"[evidence] {rec.evidence_id} · {rec.evidence_type.value} "
                    f"(source {rec.source}) · {(rec.description or '')[:120]}",
                )
            )
        events.sort(key=lambda item: item[0])
        if not events:
            return [
                AssistantSection(
                    heading="Timeline",
                    bullets=["No stored events for this wallet yet."],
                )
            ]
        return [
            AssistantSection(
                heading="Timeline (earliest → latest)",
                bullets=[line for _, line in events[:_MAX_TIMELINE_EVENTS]],
            )
        ]

    def _answer_sanctions_intelligence(self, address, chain, evidence, risk) -> List[AssistantSection]:
        """Answers "why is this wallet high risk" from PERSISTED evidence."""
        ci = None
        if risk is not None:
            ci = risk.criminal_intelligence or None
        records = [
            r
            for r in (evidence or [])
            if getattr(r, "evidence_type", None) is not None
            and r.evidence_type.value == "sanctions_match"
        ]
        source = (ci or {}).get("source") or (records[0].source if records else None)

        if not records and ci is None:
            return [
                AssistantSection(
                    heading="Criminal / Sanctions Intelligence",
                    body=(
                        "No curated public sanctions/illicit intelligence match "
                        "is recorded for this wallet."
                    ),
                    bullets=[
                        "Criminal/sanctions level: UNKNOWN / NOT ASSESSED.",
                        "Absence of a match is not evidence that the wallet is "
                        "lawful.",
                        "Sanctions data: CURATED PUBLIC INTELLIGENCE (not a "
                        "live OFAC integration).",
                    ],
                )
            ]

        entity = (ci or {}).get("entity") or "an associated entity"
        confidence = (ci or {}).get("confidence") or (
            records[0].confidence if records else "HIGH"
        )
        match_type = (ci or {}).get("match_type", "exact_address")
        evidence_id = (ci or {}).get("evidence_id") or (
            records[0].evidence_id if records else None
        )
        heading = "Criminal / Sanctions Intelligence"
        answer = (
            f"The wallet is marked HIGH RISK because the exact Ethereum "
            f"address matches a curated public sanctions/illicit intelligence "
            f"record associated with {entity}. The source is {source}. This is "
            "an investigative intelligence signal and should be independently "
            "verified."
        )
        bullets = [
            f"Level: HIGH ({match_type} match)",
            answer,
            f"Entity: {entity} · Source: {source} · Confidence: {confidence}",
            (
                f"Match type: {match_type} · Evidence id: {evidence_id}"
                if evidence_id
                else f"Match type: {match_type}"
            ),
            "Provenance: source_type=curated_public_intelligence (persisted "
            "evidence record).",
            "Sanctions data: CURATED PUBLIC INTELLIGENCE — not a live OFAC "
            "integration.",
            (
                "This does NOT claim the wallet definitely belongs to "
                f"{entity}; it means the exact address matches a curated public "
                f"sanctions/illicit intelligence record associated with {entity}."
            ),
        ]
        return [
            AssistantSection(heading=heading, body=answer, bullets=bullets)
        ]

    def _explain_risk(self, address, chain, risk) -> List[AssistantSection]:
        if risk is None:
            return [
                AssistantSection(
                    heading="Risk explanation",
                    bullets=[
                        "No risk assessment recorded for this wallet yet. "
                        "Run an analysis on the wallet first."
                    ],
                )
            ]
        bullets = [
            f"Wallet: {risk.wallet_address} · Chain: {risk.chain}",
            f"Level: {risk.level} · Score: {risk.risk_score:.0f}/100 "
            "(analytical heuristic)",
        ]
        for factor in risk.factors:
            bullets.append(
                f"- {factor.label}: {factor.detail} (weight {factor.weight:.2f})"
            )
        bullets.extend(f"- {line}" for line in risk.reasoning[:6])
        sections = [
            AssistantSection(heading="Risk explanation", bullets=bullets)
        ]
        ci = risk.criminal_intelligence
        if ci is not None:
            sections.append(
                AssistantSection(
                    heading="Criminal / Sanctions Intelligence (separate)",
                    body=(
                        ci.get("reason")
                        or "Exact address match against curated public "
                        "sanctions/illicit intelligence."
                    ),
                    bullets=[
                        f"Level: {ci.get('level')} · Entity: {ci.get('entity')} "
                        f"· Source: {ci.get('source')} · Confidence: "
                        f"{ci.get('confidence')}",
                        f"Match type: {ci.get('match_type')} · Evidence id: "
                        f"{ci.get('evidence_id') or 'UNAVAILABLE'}",
                        "Source type: curated_public_intelligence (not a live "
                        "OFAC integration).",
                        "Investigative intelligence signal; verify "
                        "independently.",
                    ],
                )
            )
        return sections

    def _assist_wallet(self, address, chain, transfers, evidence, risk) -> List[AssistantSection]:
        inbound = sum(
            1
            for t in transfers
            if (t.get("to_address") or "").lower() == address.lower()
        )
        outbound = len(transfers) - inbound
        ci = risk.criminal_intelligence if risk is not None else None
        if ci is None and evidence:
            ci = {
                "level": "high",
                "entity": [
                    r for r in evidence
                    if getattr(r, "evidence_type", None) is not None
                    and r.evidence_type.value == "sanctions_match"
                ][0].description,
            }
        sanctions_level = "HIGH (exact sanctions/illicit match)" if ci else "UNKNOWN / NOT ASSESSED"
        bullets = [
            f"Wallet: {address} · Chain: {chain}",
            f"Stored transactions: {len(transfers)} ({inbound} in / {outbound} out)",
            f"Evidence records: {len(evidence)}",
            f"Risk: {risk.level if risk else 'UNAVAILABLE'}",
            f"Criminal/sanctions intelligence: {sanctions_level}",
        ]
        if transfers:
            top = max(transfers, key=_num, default=None)
            if top:
                direction = "in" if (top.get("to_address") or "").lower() == address.lower() else "out"
                bullets.append(
                    f"Largest recorded flow: {direction.upper()} {top.get('value')} "
                    f"{_asset(top, chain)} ({top.get('tx_hash')})"
                )
        return [AssistantSection(heading="Overview", bullets=bullets)]

    # ------------------------------------------------------------------ #
    # Fund tracing / comparison
    # ------------------------------------------------------------------ #
    def _answer_trace_funds(
        self,
        request: AssistantRequest,
        ctx,
        wallet_address: Optional[str],
        wallet2: Optional[str],
        user,
    ) -> List[AssistantSection]:
        if ctx is not None:
            chain = ctx.case.network
            address = ctx.case.primary_wallet
        else:
            chain = request.chain
            address = wallet_address

        sections: List[AssistantSection] = [
            AssistantSection(
                heading="Neighbours from stored transactions",
                bullets=self._neighbour_bullets(address, chain, user),
            )
        ]

        graph = self.tools.get_graph(address, chain, user)
        self._graph_available = graph is not None
        if graph and graph.get("nodes"):
            nodes = graph["nodes"]
            sections.append(
                AssistantSection(
                    heading="Graph neighbours (Neo4j, bounded hops)",
                    bullets=[
                        f"{node.get('wallet_id') or 'UNAVAILABLE'} · depth "
                        f"{node.get('depth') or '?'}"
                        for node in nodes[:MAX_BULLETS]
                    ],
                )
            )

        if wallet2:
            path = self.tools.get_fund_flow(address, wallet2, chain)
            if path.get("found"):
                nodes = path.get("nodes") or []
                sections.append(
                    AssistantSection(
                        heading=f"Hop path to {wallet2}",
                        bullets=[
                            " → ".join(
                                str(node.get("wallet_id", "?"))[:18]
                                for node in nodes
                            ),
                            f"Hops: {path.get('total_cost')}",
                        ],
                    )
                )
            else:
                sections.append(
                    AssistantSection(
                        heading=f"Path to {wallet2}",
                        bullets=[
                            "No connecting path found within bounded stored data.",
                        ],
                    )
                )
        return sections

    def _neighbour_bullets(self, address: str, chain: str, user) -> List[str]:
        transfers = self.tools.get_transactions(address, chain, user, limit=200)
        neighbours: Dict[str, dict] = {}
        for t in transfers:
            if (t.get("to_address") or "").lower() == address.lower():
                cp = (t.get("from_address") or "").lower()
                direction = "in"
            else:
                cp = (t.get("to_address") or "").lower()
                direction = "out"
            if not cp:
                continue
            if cp not in neighbours:
                neighbours[cp] = {"direction": direction, "count": 0, "tx": t.get("tx_hash")}
            neighbours[cp]["count"] += 1
        rows = sorted(
            neighbours.items(), key=lambda item: item[1]["count"], reverse=True
        )[:MAX_BULLETS]
        if not rows:
            return ["UNAVAILABLE — no stored transactions for this wallet yet."]
        return [
            f"{cp[:16]}… · {data['direction']} · {data['count']} tx · "
            f"sample {data.get('tx', 'UNAVAILABLE')}"
            for cp, data in rows
        ]

    def _answer_compare_wallets(
        self,
        request: AssistantRequest,
        ctx,
        wallet_address: Optional[str],
        wallet2: Optional[str],
        user,
    ) -> List[AssistantSection]:
        first = wallet_address
        if ctx is not None:
            first = ctx.case.primary_wallet
        if not first or not wallet2:
            return [
                AssistantSection(
                    heading="Wallet comparison",
                    body=(
                        "Two wallet addresses are required. Provide them in the "
                        "query or via the wallet fields."
                    ),
                )
            ]
        chain = request.chain
        left = self.tools.get_wallet(first, chain, user)
        right = self.tools.get_wallet(wallet2, chain, user)
        left_tx = self.tools.get_transactions(first, chain, user)
        right_tx = self.tools.get_transactions(wallet2, chain, user)
        left_evidence = self.tools.get_evidence(first, chain, user)
        right_evidence = self.tools.get_evidence(wallet2, chain, user)

        def row_for(address, summary, tx, evidence) -> List[str]:
            return [
                address,
                f"Transactions stored: {len(tx)}",
                f"Incoming: {summary['incoming_volume'] if summary else 'UNAVAILABLE'}",
                f"Outgoing: {summary['outgoing_volume'] if summary else 'UNAVAILABLE'}",
                f"Risk: {summary['risk'] if summary else 'UNAVAILABLE'}",
                f"Evidence records: {len(evidence)}",
            ]

        return [
            AssistantSection(heading="Wallet A", bullets=row_for(first, left, left_tx, left_evidence)),
            AssistantSection(heading="Wallet B", bullets=row_for(wallet2, right, right_tx, right_evidence)),
            AssistantSection(
                heading="Comparison",
                bullets=self._comparison_deltas(first, wallet2, left_tx, right_tx),
            ),
        ]

    @staticmethod
    def _comparison_deltas(left, right, left_tx, right_tx) -> List[str]:
        lv = sum(_num(t.get("value")) for t in left_tx)
        rv = sum(_num(t.get("value")) for t in right_tx)
        deltas = [
            f"Transaction volume: {left[:12]}…={lv:.4g}, {right[:12]}…={rv:.4g}",
            f"Degree of stored activity: {len(left_tx)} vs {len(right_tx)}",
        ]
        return deltas

    # ------------------------------------------------------------------ #
    # No-scope guidance
    # ------------------------------------------------------------------ #
    @staticmethod
    def _answer_no_scope() -> List[AssistantSection]:
        return [
            AssistantSection(
                heading="Scope needed",
                body=(
                    "This assistant answers from authorized, persisted "
                    "investigation data. Provide a case id or a wallet address "
                    "to get a grounded answer."
                ),
                bullets=[
                    "Open a case or wallet first, then ask again.",
                    "Suggested actions are offered below.",
                ],
            )
        ]

    # ------------------------------------------------------------------ #
    # Runtime collection (evidence ids / tx hashes / data source policy)
    # ------------------------------------------------------------------ #
    def _collect_runtime(
        self,
        intent: str,
        case_id: Optional[str],
        ctx,
        record: Optional[dict],
        wallet_address: Optional[str],
        user,
    ) -> Tuple[List[str], List[str], str]:
        evidence: List[str] = []
        tx_hashes: List[str] = []

        if ctx is not None:
            evidence.extend(r.evidence_id for r in ctx.evidence)
            for candidate in self.tools.get_case_candidates(record) if record else []:
                evidence.extend(candidate.get("evidence_ids") or [])
            for t in self.tools.get_case_transactions(ctx):
                if t.get("tx_hash"):
                    tx_hashes.append(str(t["tx_hash"]))
        if wallet_address and ctx is None:
            chain = "eth"
            for r in self.tools.get_evidence(wallet_address, chain, user):
                evidence.append(r.evidence_id)
            for t in self.tools.get_transactions(wallet_address, chain, user, limit=200):
                if t.get("tx_hash"):
                    tx_hashes.append(str(t["tx_hash"]))

        evidence = list(dict.fromkeys(evidence))
        tx_hashes = list(dict.fromkeys(tx_hashes))[:200]

        data_source = "unavailable"
        if ctx is not None:
            sources = {
                getattr(r, "source", "") for r in ctx.evidence if getattr(r, "source", "")
            }
            if sources:
                data_source = self._data_source_from_sources(sources)
            elif ctx.case.data_source in {"live", "demo", "mixed"}:
                data_source = ctx.case.data_source
        elif wallet_address:
            records = self.tools.get_evidence(wallet_address, "eth", user)
            sources = {
                getattr(r, "source", "") for r in records if getattr(r, "source", "")
            }
            if sources:
                data_source = self._data_source_from_sources(sources)
        return evidence, tx_hashes, data_source

    @staticmethod
    def _data_source_from_sources(sources) -> str:
        if sources == {"chain"}:
            return "live"
        if sources == {"synthetic"}:
            return "demo"
        return "mixed"

    def _warnings_for(self, data_source: str, intent: str) -> List[str]:
        warnings: List[str] = []
        if data_source == "demo":
            warnings.append(DEMO_WARNING)
        elif data_source == "mixed":
            warnings.append(MIXED_WARNING)
        elif data_source == "unavailable":
            warnings.append(UNAVAILABLE_WARNING)
        if intent == "trace_funds" and self._graph_available is False:
            warnings.append(GRAPH_WARNING)
        if intent == "prepare_referral":
            warnings.append(REFERRAL_WARNING)
        if intent == "suspicious_transactions":
            warnings.append(SUSPICIOUS_WARNING)
        return warnings

    def _suggested_actions(
        self, case_id: Optional[str], wallet_address: Optional[str]
    ) -> List[AssistantQuickAction]:
        has_case = bool(case_id)
        has_wallet = bool(wallet_address) or has_case
        return [
            action
            for action in QUICK_ACTIONS
            if (has_wallet and action.scope == "wallet")
            or (has_case and action.scope == "case")
        ][:8]

    # ------------------------------------------------------------------ #
    # Referral draft
    # ------------------------------------------------------------------ #
    def _build_referral_draft(self, ctx, record: Optional[dict]) -> ReferralDraft:
        case = ctx.case
        evidence_ids = [r.evidence_id for r in ctx.evidence]
        for candidate in self.tools.get_case_candidates(record) if record else []:
            evidence_ids.extend(candidate.get("evidence_ids") or [])
        evidence_ids = list(dict.fromkeys(evidence_ids))
        tx_hashes = [
            str(t["tx_hash"])
            for t in self.tools.get_case_transactions(ctx)
            if t.get("tx_hash")
        ][:200]
        vasp = [
            str(c.get("vasp_name"))
            for c in self.tools.get_case_candidates(record) if record
            if c.get("vasp_name")
        ][:10]
        summary = (
            f"Case {case.name} ({case.id}) investigates wallet "
            f"{case.primary_wallet} on {case.network}. {len(tx_hashes)} "
            f"transactions and {len(evidence_ids)} evidence records are "
            f"available for review. Stored risk level: {case.risk}."
        )
        score = ctx.risk.risk_score if ctx.risk is not None else None
        return ReferralDraft(
            title=f"Referral draft — {case.name}",
            case_id=case.id,
            primary_wallet=case.primary_wallet,
            chain=case.network,
            summary=summary,
            evidence_ids=evidence_ids,
            transaction_hashes=tx_hashes,
            vasp_candidates=vasp,
            risk_level=case.risk or "unknown",
            risk_score=score,
            submission_state="requires_sahyog_connection",
            sahyog_status="integration-ready",
        )