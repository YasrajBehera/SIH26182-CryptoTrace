"""Tests for the M9 Investigator Intelligence Assistant.

Focus: RBAC gating, case-ownership scoping, evidence-grounded answers
(no fabrication), free-text intent parsing, quick actions, and the draft
referral policy (draft only, never submitted).
"""

import pytest

from app import models
from assistant.models import AssistantRequest
from assistant.service import AssistantService
from assistant.tools import AssistantTools
from cases.models import InvestigationCreate
from cases.repository import MemoryInvestigationRepository
from cases.service import InvestigationService
from evidence.models import EvidenceRecord, EvidenceType, Provenance
from evidence.repository import EvidenceRepository
from evidence.service import EvidenceService
from risk.repository import MemoryRiskRepository
from risk.service import RiskService
from wallets.repository import MemoryWalletRepository
from wallets.service import WalletService

ADDR = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
OTHER_ADDR = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

WALLET_SEED = [
    {
        "tx_hash": "0xaaa1",
        "chain": "eth",
        "block_number": 18999999,
        "block_timestamp": 1704067200,
        "from_address": OTHER_ADDR,
        "to_address": ADDR,
        "value": "10000",
        "token_symbol": "USDT",
    },
    {
        "tx_hash": "0xaaa2",
        "chain": "eth",
        "block_number": 19000000,
        "block_timestamp": 1704067300,
        "from_address": ADDR,
        "to_address": OTHER_ADDR,
        "value": "5000",
        "token_symbol": "USDT",
    },
    {
        "tx_hash": "0xaaa3",
        "chain": "eth",
        "block_number": 19000001,
        "block_timestamp": 1704067400,
        "from_address": OTHER_ADDR,
        "to_address": ADDR,
        "value": "3000",
        "token_symbol": "USDT",
    },
]


def _user(uid=1, role="admin", username="admin"):
    return models.User(
        id=uid,
        username=username,
        role=role,
        title="Investigator",
        display_name=username,
        password_hash="x",
    )


def _make_case(svc, name="Alpha"):
    return svc.tools.investigations.create(
        InvestigationCreate(name=name, primary_wallet=ADDR, network="eth"),
        _user(uid=1),
    )


def _apply_case(svc, case_id):
    svc.tools.investigations.apply_analysis(
        case_id=case_id,
        address=ADDR,
        analysis_id="attr-m9",
        data_source="live",
        candidates=[
            {
                "vasp_name": "Binance",
                "score": 82.0,
                "confidence": "HIGH",
                "score_breakdown": {"known_address_match": 50},
                "evidence_ids": [],
                "explanation": ["Direct known-address match with Binance."],
            }
        ],
        transactions=list(WALLET_SEED),
        user=_user(uid=1),
    )


def _assistant_service() -> AssistantService:
    """Fully-isolated assistant wired to fresh in-memory stores per test.

    The investigation service and the tools share the same evidence, wallet
    and risk stores, mirroring the dependency-injected wiring the API uses.
    """
    wallets_repo = MemoryWalletRepository()
    risk_repo = MemoryRiskRepository()
    evidence_svc = EvidenceService(repository=EvidenceRepository())
    cases_svc = InvestigationService(
        repository=MemoryInvestigationRepository(),
        evidence_service=evidence_svc,
        wallet_repository=wallets_repo,
        risk_repository=risk_repo,
    )
    tools = AssistantTools(
        investigations=cases_svc,
        wallets=WalletService(repository=wallets_repo),
        evidence=evidence_svc,
        risk=RiskService(repository=risk_repo),
    )
    return AssistantService(tools=tools)


class TestIntentParsing:
    def test_quick_actions_are_offered(self):
        actions = AssistantService().quick_actions()
        ids = [a.id for a in actions]
        assert "summarize_case" in ids
        assert "prepare_referral" in ids
        assert "what_changed" in ids
        assert "compare_wallets" in ids
        assert all(a.scope in {"case", "wallet"} for a in actions)

    @pytest.mark.parametrize(
        "text,intent",
        [
            ("what is the summary of this case", "summarize_case"),
            ("track where the funds went", "trace_funds"),
            ("which exchange is this wallet tied to", "find_vasp"),
            ("why is Binance ranked highest", "explain_attribution"),
            ("flag suspicious or large transactions", "suspicious_transactions"),
            ("build a chronological timeline", "build_timeline"),
            ("explain the risk score please", "explain_risk"),
            ("generate a report for export", "generate_report"),
            ("prepare a lawful referral to SAHYOG", "prepare_referral"),
            ("compare the two wallets", "compare_wallets"),
            ("what changed since the last update", "what_changed"),
            ("这是案件总结", "summarize_case"),
            ("解释一下风险", "explain_risk"),
            ("追踪资金流向", "trace_funds"),
        ],
    )
    def test_free_text_intent_mapping(self, text, intent):
        svc = _assistant_service()
        assert svc._resolve_intent(AssistantRequest(query=text), "") == intent

    def test_explicit_intent_hint_wins(self):
        svc = _assistant_service()
        resolved = svc._resolve_intent(
            AssistantRequest(query="zeta seed", intent="summarize_case"), "0x1"
        )
        assert resolved == "summarize_case"

    def test_unknown_text_defaults_to_assist(self):
        svc = _assistant_service()
        assert svc._resolve_intent(AssistantRequest(query="hello world"), "") == "assist"


class TestCaseScopedAnswers:
    def test_summarize_grounds_answer_in_case_data(self):
        svc = _assistant_service()
        case = _make_case(svc)
        _apply_case(svc, case.id)
        resp = svc.interact(
            AssistantRequest(query="summary", intent="summarize_case", case_id=case.id),
            _user(uid=1),
        )
        assert resp.intent == "summarize_case"
        assert resp.data_source == "live"
        assert resp.human_review_required is True
        assert resp.disclaimer
        all_bullets = " ".join(b for s in resp.sections for b in s.bullets)
        assert case.primary_wallet in all_bullets
        assert "Binance" in all_bullets
        assert "82.0" in all_bullets

    def test_summarize_empty_case_is_honest(self):
        svc = _assistant_service()
        case = _make_case(svc)
        resp = svc.interact(
            AssistantRequest(query="summary", intent="summarize_case", case_id=case.id),
            _user(uid=1),
        )
        all_bullets = " ".join(b for s in resp.sections for b in s.bullets)
        assert "No analysis has been applied" in all_bullets

    def test_non_owner_case_is_not_visible(self):
        svc = _assistant_service()
        case = _make_case(svc)
        with pytest.raises(Exception) as err:
            svc.interact(
                AssistantRequest(query="summary", intent="summarize_case", case_id=case.id),
                _user(uid=9, role="investigator", username="investigator"),
            )
        from cases.service import CaseNotFoundError

        assert isinstance(err.value, CaseNotFoundError)

    def test_prepare_referral_is_draft_only(self):
        svc = _assistant_service()
        case = _make_case(svc)
        _apply_case(svc, case.id)
        resp = svc.interact(
            AssistantRequest(query="referral", intent="prepare_referral", case_id=case.id),
            _user(uid=1),
        )
        draft = resp.referral_draft
        assert draft is not None
        assert draft.case_id == case.id
        assert draft.primary_wallet == ADDR
        assert draft.submission_state == "requires_sahyog_connection"
        assert draft.sahyog_status == "integration-ready"
        assert all(h.startswith("0x") for h in draft.transaction_hashes)
        assert "Binance" in draft.vasp_candidates
        assert "Draft referral" in resp.title
        assert any("No submission" in w for w in resp.warnings)

    def test_what_changed_reports_no_change_when_synced(self):
        svc = _assistant_service()
        case = _make_case(svc)
        _apply_case(svc, case.id)
        resp = svc.interact(
            AssistantRequest(query="changed?", intent="what_changed", case_id=case.id),
            _user(uid=1),
        )
        bullets = " ".join(b for s in resp.sections for b in s.bullets)
        assert "No changes" in bullets


class TestWalletScopedAnswers:
    def test_find_vasp_without_analysis_is_unavailable(self):
        svc = _assistant_service()
        resp = svc.interact(
            AssistantRequest(query="find vasp", intent="find_vasp", wallet_address=ADDR),
            _user(uid=1),
        )
        assert resp.data_source == "unavailable"
        bullets = " ".join(b for s in resp.sections for b in s.bullets)
        assert "UNAVAILABLE" in bullets

    def test_suspicious_review_computes_flags_from_stored_data(self):
        svc = _assistant_service()
        svc.tools.wallets.repository.store_transactions(WALLET_SEED)
        resp = svc.interact(
            AssistantRequest(
                query="suspicious",
                intent="suspicious_transactions",
                wallet_address=ADDR,
                chain="eth",
            ),
            _user(uid=1),
        )
        bullets = " ".join(b for s in resp.sections for b in s.bullets)
        assert "Stored transactions: 3" in bullets
        assert "10000" in bullets
        assert "Aggregate value" in bullets
        assert any(
            "heuristic" in w.lower() or "review" in w.lower() for w in resp.warnings
        )

    def test_explain_risk_falls_back_to_no_assessment(self):
        svc = _assistant_service()
        resp = svc.interact(
            AssistantRequest(query="risk", intent="explain_risk", wallet_address=ADDR),
            _user(uid=1),
        )
        bullets = " ".join(b for s in resp.sections for b in s.bullets)
        assert "No risk assessment recorded" in bullets

    def test_timeline_sorts_transfers_and_evidence(self):
        svc = _assistant_service()
        svc.tools.wallets.repository.store_transactions(WALLET_SEED)
        prov = Provenance(created_at="2025-12-31T00:00:00Z", method="test")
        svc.tools.evidence.repository.store(
            EvidenceRecord(
                evidence_id="ev-m9-timeline",
                attribution_id="attr-x",
                evidence_type=EvidenceType.KNOWN_ADDRESS_MATCH,
                address=ADDR,
                chain="eth",
                source="synthetic",
                confidence=0.5,
                description="test signal",
                provenance=prov,
            )
        )
        resp = svc.interact(
            AssistantRequest(query="timeline", intent="build_timeline", wallet_address=ADDR),
            _user(uid=1),
        )
        bullets = " ".join(b for s in resp.sections for b in s.bullets)
        assert "0xaaa1" in bullets
        assert "ev-m9-timeline" in bullets


class TestToolsWiring:
    def test_tools_share_the_injected_stores(self):
        wallets_repo = MemoryWalletRepository()
        risk_repo = MemoryRiskRepository()
        evidence_svc = EvidenceService(repository=EvidenceRepository())
        cases_svc = InvestigationService(
            repository=MemoryInvestigationRepository(),
            evidence_service=evidence_svc,
            wallet_repository=wallets_repo,
            risk_repository=risk_repo,
        )
        tools = AssistantTools(
            investigations=cases_svc,
            wallets=WalletService(repository=wallets_repo),
            evidence=evidence_svc,
            risk=RiskService(repository=risk_repo),
        )
        assert tools.investigations is cases_svc
        assert tools.wallets.repository is wallets_repo
        assert tools.evidence is evidence_svc
        assert tools.risk.repository is risk_repo


class TestAssistantAPI:
    def test_requires_authentication(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from assistant.api import router

        test_app = FastAPI(title="assistant-401-test")
        test_app.include_router(router)
        client = TestClient(test_app)
        resp = client.post("/api/v1/assistant/query", json={"query": "summary"})
        assert resp.status_code == 401
        resp2 = client.get("/api/v1/assistant/quick-actions")
        assert resp2.status_code == 401

    def test_quick_actions_endpoint(self, app_client):
        resp = app_client.get("/api/v1/assistant/quick-actions")
        assert resp.status_code == 200
        ids = [a["id"] for a in resp.json()]
        assert len(ids) >= 10
        assert "summarize_case" in ids

    def test_summarize_case_via_api(self, app_client):
        case = app_client.post(
            "/api/v1/investigations",
            json={"name": "assistant api case", "primary_wallet": ADDR},
        ).json()
        app_client._test_wallets_repo.store_transactions(WALLET_SEED)
        resp = app_client.post(
            "/api/v1/assistant/query",
            json={
                "query": "summary of the case",
                "intent": "summarize_case",
                "case_id": case["id"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "summarize_case"
        assert data["data_source"] in {"live", "demo", "mixed", "unavailable"}
        assert data["human_review_required"] is True
        assert data["request_id"].startswith("asr-")
        assert data["suggested_actions"]

    def test_case_ownership_is_enforced_on_assistant(self, app_client):
        from app.auth.deps import get_current_user

        case = app_client.post(
            "/api/v1/investigations",
            json={"name": "owned case", "primary_wallet": ADDR},
        ).json()
        other = models.User(
            id=9001,
            username="investigator",
            role="investigator",
            title="Investigator",
            display_name="investigator",
            password_hash="x",
        )
        app_client.app.dependency_overrides[get_current_user] = lambda: other
        resp = app_client.post(
            "/api/v1/assistant/query",
            json={"query": "summary", "case_id": case["id"]},
        )
        assert resp.status_code == 404

    def test_prepare_referral_via_api(self, app_client):
        case = app_client.post(
            "/api/v1/investigations",
            json={"name": "referral case", "primary_wallet": ADDR},
        ).json()
        resp = app_client.post(
            "/api/v1/assistant/query",
            json={"intent": "prepare_referral", "case_id": case["id"], "query": "referral"},
        )
        assert resp.status_code == 200
        draft = resp.json()["referral_draft"]
        assert draft is not None
        assert draft["submission_state"] == "requires_sahyog_connection"

    def test_trace_funds_uses_graph_driver_when_available(self, app_client):
        resp = app_client.post(
            "/api/v1/assistant/query",
            json={"intent": "trace_funds", "wallet_address": ADDR, "query": "trace"},
        )
        assert resp.status_code == 200
        data = resp.json()
        headings = [s["heading"] for s in data["sections"]]
        assert any("Graph neighbours" in h for h in headings)
        assert not any("Neo4j" in w for w in data["warnings"])

    def test_trace_funds_target_path_section(self, app_client):
        app_client._test_wallets_repo.store_transactions(WALLET_SEED)
        resp = app_client.post(
            "/api/v1/assistant/query",
            json={
                "intent": "trace_funds",
                "wallet_address": ADDR,
                "wallet2": OTHER_ADDR,
                "query": "path",
            },
        )
        assert resp.status_code == 200
        headings = " ".join(s["heading"] for s in resp.json()["sections"])
        assert "Hop path" in headings

    def test_audit_result_column_holds_composed_verdicts(self, app_client):
        # Regression: the audit `result` column used to be VARCHAR(16), so
        # composed verdicts such as "prepare_referral:unavailable" (21 chars)
        # or "13:<case_id>" overflowed and surfaced as a 500 on the assistant
        # and report routes. The column must stay wide enough for these.
        from sqlalchemy import String

        from app.models import AuditLog

        column_type = AuditLog.__table__.c.result.type
        assert isinstance(column_type, String)
        assert column_type.length >= len("prepare_referral:unavailable")