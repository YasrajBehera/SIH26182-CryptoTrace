"""Tests for the global search module and the investigation context endpoint.

Uses the deterministic in-memory repositories so results are predictable and
no live provider/database is required.
"""

from __future__ import annotations

from cases.repository import MemoryInvestigationRepository
from evidence.models import EvidenceType
from evidence.repository import EvidenceRepository
from evidence.service import EvidenceService
from search.service import SearchService
from wallets.repository import MemoryWalletRepository


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
def _seed() -> tuple:
    cases = MemoryInvestigationRepository()
    case = cases.create(
        {
            "name": "Operation Dark Ripple",
            "description": "Suspected laundering ring",
            "primary_wallet": "0x1111111111111111111111111111111111111111",
            "network": "eth",
            "priority": "high",
            "created_by": 1,
            "tags": ["laundering"],
        }
    )
    case_id = case["id"]
    cases.update(case_id, {"latest_analysis_id": "attr-seedcase1234"})

    wallets = MemoryWalletRepository()
    wallets.store_transactions(
        [
            {
                "chain": "eth",
                "tx_hash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234abcd",
                "block_timestamp": 1700000000,
                "from_address": "0x1111111111111111111111111111111111111111",
                "to_address": "0x2222222222222222222222222222222222222222",
                "value": "1000",
            }
        ]
    )
    wallets.upsert_summary(
        {
            "address": "0x1111111111111111111111111111111111111111",
            "chain": "eth",
            "transaction_count": 1,
            "risk": "high",
        }
    )

    evidence_svc = EvidenceService(repository=EvidenceRepository())
    ev = evidence_svc.create_evidence(
        attribution_id="attr-evidenceA1",
        evidence_type=EvidenceType.KNOWN_ADDRESS_MATCH,
        address="0x1111111111111111111111111111111111111111",
        chain="eth",
        confidence=0.9,
        description="Direct match with a known VASP address",
        tx_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234abcd",
        method="attribution_engine_v1",
    )

    service = SearchService(
        investigation_repository=cases,
        wallet_repository=wallets,
        evidence_service=evidence_svc,
    )
    return service, case, wallets, evidence_svc, ev


# --------------------------------------------------------------------------- #
# Service-level search
# --------------------------------------------------------------------------- #
class TestGlobalSearch:
    def test_empty_query_returns_nothing(self):
        service, *_ = _seed()
        assert service.search("") == []

    def test_search_investigation_by_name(self):
        service, case, *_ = _seed()
        results = service.search("dark ripple")
        assert any(r.entity_type == "investigation" and r.id == case["id"] for r in results)
        hit = next(r for r in results if r.entity_type == "investigation")
        assert hit.url == f"/investigations/{case['id']}"
        assert hit.metadata["wallet"] == case["primary_wallet"]

    def test_search_wallet_by_address(self):
        service, *_ = _seed()
        results = service.search("0x11111111")
        wallets_hits = [r for r in results if r.entity_type == "wallet"]
        assert wallets_hits
        assert wallets_hits[0].url == "/wallets/0x1111111111111111111111111111111111111111"

    def test_search_transaction_by_hash(self):
        service, *_ = _seed()
        results = service.search("0xabcdef1234")
        txs = [r for r in results if r.entity_type == "transaction"]
        assert txs
        assert txs[0].url.startswith("/transactions?hash=")

    def test_search_evidence_and_attribution(self):
        service, *_ = _seed()
        results = service.search("ev-")
        assert any(r.entity_type == "evidence" for r in results)
        analysis_results = service.search("attr-")
        assert any(r.entity_type == "attribution" for r in analysis_results)

    def test_entity_type_restriction(self):
        service, *_ = _seed()
        results = service.search("1111", entity_types=["wallet"])
        assert results
        assert all(r.entity_type == "wallet" for r in results)

    def test_max_hits_capped(self):
        service, *_ = _seed()
        results = service.search("0x111", limit=1)
        assert len(results) == 1

    def test_relevance_orders_prefix_matches_first(self):
        service, *_ = _seed()
        results = service.search("0xabcdef123456")
        assert results[0].entity_type == "transaction"
        assert results[0].id.startswith("0xabcdef123456")


# --------------------------------------------------------------------------- #
# API-level search
# --------------------------------------------------------------------------- #
def _seed_api_state(app_client) -> str:
    """Seed the DI-injected in-memory stores the API actually reads."""
    wallets = app_client._test_wallets_repo
    wallets.upsert_summary(
        {
            "address": "0x1111111111111111111111111111111111111111",
            "chain": "eth",
            "transaction_count": 1,
            "risk": "high",
        }
    )
    case = app_client._test_cases_repo.create(
        {
            "name": "Operation Alpha Ledger",
            "description": "API-level search case",
            "primary_wallet": "0x1111111111111111111111111111111111111111",
            "network": "eth",
            "priority": "high",
            "created_by": 1,
            "tags": ["structured"],
        }
    )
    return case["id"]


class TestSearchApi:
    def test_search_returns_entity_type(self, app_client):
        _seed_api_state(app_client)
        resp = app_client.get("/api/v1/search", params={"q": "0x11111111"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] > 0
        types = {r["entity_type"] for r in body["results"]}
        assert "wallet" in types

    def test_search_finds_cases(self, app_client):
        case_id = _seed_api_state(app_client)
        resp = app_client.get("/api/v1/search", params={"q": "alpha ledger"})
        assert resp.status_code == 200
        hits = [r for r in resp.json()["results"] if r["entity_type"] == "investigation"]
        assert any(r["id"] == case_id for r in hits)

    def test_search_requires_authentication(self, app_client):
        """The endpoint is gated by search.read; an unauthenticated call
        must fail even when the query is valid."""
        from fastapi import HTTPException
        from app.auth.deps import get_current_user

        overrides = dict(app_client.app.dependency_overrides)

        def _unauth():
            raise HTTPException(status_code=401, detail="Not authenticated")

        app_client.app.dependency_overrides[get_current_user] = _unauth
        try:
            resp = app_client.get("/api/v1/search", params={"q": "0x11111111"})
        finally:
            app_client.app.dependency_overrides.clear()
            app_client.app.dependency_overrides.update(overrides)
        assert resp.status_code == 401

    def test_search_records_audit_event(self, app_client):
        from app.audit.repository import make_audit_log_repository

        app_client.get("/api/v1/search", params={"q": "0x11111111"})
        repo = make_audit_log_repository()
        events = repo.list(action="SEARCH")
        assert len(events) >= 1
        assert events[-1].action == "SEARCH"


# --------------------------------------------------------------------------- #
# Investigation context endpoint
# --------------------------------------------------------------------------- #
class TestCaseContext:
    def test_context_aggregates_persisted_data(self, app_client):
        # Create a case through the API then attach analysis-like state.
        create = app_client.post(
            "/api/v1/investigations",
            json={
                "name": "Context Case",
                "description": "for context tests",
                "primary_wallet": "0x3333333333333333333333333333333333333333",
                "network": "eth",
            },
        )
        assert create.status_code == 201
        case_id = create.json()["id"]

        app_client.patch(
            f"/api/v1/investigations/{case_id}",
            json={"latest_report_ids": [], "status": "review"},
        )
        resp = app_client.get(f"/api/v1/investigations/{case_id}/context")
        assert resp.status_code == 200
        body = resp.json()
        assert body["case"]["id"] == case_id
        assert "wallet_summary" in body
        assert "scope" in body

    def test_context_unknown_case_returns_404(self, app_client):
        resp = app_client.get("/api/v1/investigations/case-doesnotexist/context")
        assert resp.status_code == 404

    def test_attach_report_id_records_on_case(self, app_client):
        """Report ids travel through InvestigationService.attach_report (the
        path the reports exporter uses), not the generic case PATCH."""
        from cases.service import InvestigationService
        from types import SimpleNamespace

        admin = SimpleNamespace(role="admin", id=1, username="admin")
        cases = MemoryInvestigationRepository()
        wallets = MemoryWalletRepository()
        case = cases.create(
            {
                "name": "Report Case",
                "primary_wallet": "0x4444444444444444444444444444444444444444",
                "network": "eth",
                "created_by": 1,
            }
        )
        service = InvestigationService(
            repository=cases,
            wallet_repository=wallets,
        )
        updated = service.attach_report(case["id"], "rpt-0001", admin)
        assert "rpt-0001" in updated.latest_report_ids
        assert updated.latest_analysis_id is None