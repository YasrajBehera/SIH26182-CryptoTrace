"""Tests for the investigation (case) CRUD + analysis-binding surface."""

import pytest

from app import models
from cases.models import (
    ApplyAnalysisRequest,
    InvestigationCreate,
    InvestigationNoteCreate,
    InvestigationUpdate,
)
from cases.repository import MemoryInvestigationRepository
from cases.service import (
    CaseAccessError,
    CaseConflictError,
    CaseNotFoundError,
    InvestigationService,
)
from evidence.models import EvidenceRecord, EvidenceType, Provenance
from evidence.repository import EvidenceRepository
from risk.repository import MemoryRiskRepository
from wallets.repository import MemoryWalletRepository

ADDR = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
OTHER_ADDR = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def _user(uid=1, role="admin", username="admin"):
    return models.User(
        id=uid,
        username=username,
        role=role,
        title="Investigator",
        display_name=username,
        password_hash="x",
    )


def _service():
    return InvestigationService(
        repository=MemoryInvestigationRepository(),
        evidence_service=EvidenceServiceForTest(),
        wallet_repository=MemoryWalletRepository(),
        risk_repository=MemoryRiskRepository(),
    )


class EvidenceServiceForTest:
    def __init__(self):
        self.repo = EvidenceRepository()

    def link_to_investigation(self, attribution_id, investigation_id):
        linked = []
        for record in self.repo.get_by_attribution(attribution_id):
            updated = record.model_copy(update={"investigation_id": investigation_id})
            self.repo.store(updated)
            linked.append(updated)
        return linked

    def get_evidence_for_investigation(self, investigation_id):
        return self.repo.get_by_investigation(investigation_id)

    def seed(self, attribution_id, count=2):
        prov = Provenance(created_at="2025-01-01T00:00:00Z", method="test")
        for i in range(count):
            self.repo.store(
                EvidenceRecord(
                    evidence_id=f"ev-{attribution_id}-{i}",
                    attribution_id=attribution_id,
                    evidence_type=EvidenceType.GRAPH_PROXIMITY,
                    address=ADDR,
                    chain="eth",
                    confidence=0.7,
                    provenance=prov,
                )
            )


class TestCaseService:
    def test_create_case(self):
        svc = _service()
        out = svc.create(
            InvestigationCreate(name="Alpha", primary_wallet=ADDR, network="eth"),
            _user(),
        )
        assert out.id.startswith("case-")
        assert out.name == "Alpha"
        assert out.primary_wallet == ADDR
        assert out.status == "open"
        assert out.risk == "unknown"
        assert out.data_source == "demo"

    def test_get_returns_same_case(self):
        svc = _service()
        created = svc.create(
            InvestigationCreate(name="Alpha", primary_wallet=ADDR), _user(uid=7)
        )
        fetched = svc.get(created.id, _user(uid=7))
        assert fetched.id == created.id

    def test_non_owner_cannot_read_hidden_case(self):
        svc = _service()
        created = svc.create(
            InvestigationCreate(name="Alpha", primary_wallet=ADDR), _user(uid=7)
        )
        with pytest.raises(CaseNotFoundError):
            svc.get(created.id, _user(uid=8, role="investigator"))

    def test_admin_can_read_any_case(self):
        svc = _service()
        created = svc.create(
            InvestigationCreate(name="Alpha", primary_wallet=ADDR), _user(uid=7)
        )
        fetched = svc.get(created.id, _user(uid=1, role="admin"))
        assert fetched.id == created.id

    def test_list_scopes_to_owner(self):
        svc = _service()
        svc.create(InvestigationCreate(name="mine", primary_wallet=ADDR), _user(uid=1))
        svc.create(InvestigationCreate(name="yours", primary_wallet=ADDR), _user(uid=9))
        all_cases = svc.list(_user(uid=1, role="admin"))
        assert len(all_cases.investigations) == 2
        own_cases = svc.list(_user(uid=1, role="investigator"))
        assert len(own_cases.investigations) == 1
        assert own_cases.investigations[0].name == "mine"

    def test_update_fields(self):
        svc = _service()
        created = svc.create(
            InvestigationCreate(name="Alpha", primary_wallet=ADDR), _user()
        )
        updated = svc.update(
            created.id,
            InvestigationUpdate(status="review", priority="high", tags=["x"]),
            _user(),
        )
        assert updated.status == "review"
        assert updated.priority == "high"
        assert updated.tags == ["x"]

    def test_delete_removes_case(self):
        svc = _service()
        created = svc.create(
            InvestigationCreate(name="Alpha", primary_wallet=ADDR), _user()
        )
        assert svc.delete(created.id, _user()) is True
        with pytest.raises(CaseNotFoundError):
            svc.get(created.id, _user())

    def test_apply_analysis_links_evidence_and_risk(self):
        svc = _service()
        created = svc.create(
            InvestigationCreate(name="Alpha", primary_wallet=ADDR), _user()
        )
        svc._evidence.seed("attr-1", count=3)
        out = svc.apply_analysis(
            case_id=created.id,
            address=ADDR,
            analysis_id="attr-1",
            data_source="live",
            candidates=[
                {
                    "vasp_name": "Binance",
                    "score": 82.0,
                    "confidence": "HIGH",
                    "score_breakdown": {"known_address_match": 50},
                }
            ],
            transactions=[
                {
                    "tx_hash": "0x1",
                    "chain": "eth",
                    "block_timestamp": 1704067200,
                    "from_address": ADDR,
                    "to_address": "0xcc",
                    "value": "100",
                }
            ],
            user=_user(),
        )
        assert out.status == "investigating"
        assert out.evidence_count == 3
        assert out.transactions == 1
        assert out.vasp_candidates == 1
        assert out.data_source == "live"
        assert out.risk in {"critical", "high", "medium", "low", "unknown"}
        linked = svc._evidence.repo.get_by_investigation(created.id)
        assert len(linked) == 3

    def test_apply_analysis_rejects_mismatched_wallet(self):
        svc = _service()
        created = svc.create(
            InvestigationCreate(name="Alpha", primary_wallet=ADDR), _user()
        )
        with pytest.raises(CaseConflictError):
            svc.apply_analysis(
                case_id=created.id,
                address=OTHER_ADDR,
                analysis_id="attr-1",
                data_source="live",
                user=_user(),
            )

    def test_analyst_can_create_case(self):
        svc = _service()
        out = svc.create(
            InvestigationCreate(name="Analyst build", primary_wallet=ADDR),
            _user(uid=5, role="analyst", username="analyst"),
        )
        assert out.id.startswith("case-")

    def test_analyst_can_read_any_case(self):
        svc = _service()
        created = svc.create(
            InvestigationCreate(name="Alpha", primary_wallet=ADDR), _user(uid=7)
        )
        fetched = svc.get(created.id, _user(uid=5, role="analyst", username="analyst"))
        assert fetched.id == created.id

    def test_reviewer_can_read_any_case(self):
        svc = _service()
        created = svc.create(
            InvestigationCreate(name="Alpha", primary_wallet=ADDR), _user(uid=7)
        )
        fetched = svc.get(created.id, _user(uid=6, role="reviewer", username="reviewer"))
        assert fetched.id == created.id

    def test_analyst_list_sees_all_cases(self):
        svc = _service()
        svc.create(InvestigationCreate(name="mine", primary_wallet=ADDR), _user(uid=7))
        svc.create(InvestigationCreate(name="yours", primary_wallet=ADDR), _user(uid=9))
        listing = svc.list(_user(uid=5, role="analyst", username="analyst"))
        assert len(listing.investigations) == 2

    def test_analyst_cannot_update_foreign_case(self):
        svc = _service()
        created = svc.create(
            InvestigationCreate(name="Alpha", primary_wallet=ADDR), _user(uid=7)
        )
        with pytest.raises(CaseAccessError):
            svc.update(
                created.id,
                InvestigationUpdate(status="review"),
                _user(uid=5, role="analyst", username="analyst"),
            )

    def test_analyst_cannot_apply_analysis_to_foreign_case(self):
        svc = _service()
        created = svc.create(
            InvestigationCreate(name="Alpha", primary_wallet=ADDR), _user(uid=7)
        )
        with pytest.raises(CaseAccessError):
            svc.apply_analysis(
                case_id=created.id,
                address=ADDR,
                analysis_id="attr-1",
                data_source="live",
                user=_user(uid=5, role="analyst", username="analyst"),
            )

    def test_context_scope_for_read_all_roles(self):
        svc = _service()
        created = svc.create(
            InvestigationCreate(name="Alpha", primary_wallet=ADDR), _user(uid=7)
        )
        analyst = svc.context(
            created.id, _user(uid=5, role="analyst", username="analyst")
        )
        reviewer = svc.context(
            created.id, _user(uid=6, role="reviewer", username="reviewer")
        )
        assert analyst.scope == "read_all"
        assert reviewer.scope == "read_all"

    def test_persisted_transactions_is_unique_wallet_count(self):
        svc = _service()
        created = svc.create(
            InvestigationCreate(name="Alpha", primary_wallet=ADDR), _user()
        )
        out = svc.apply_analysis(
            case_id=created.id,
            address=ADDR,
            analysis_id="attr-1",
            data_source="live",
            transactions=[
                {
                    "tx_hash": "0xdup",
                    "chain": "eth",
                    "block_timestamp": 1704067200,
                    "from_address": ADDR,
                    "to_address": "0xcc",
                    "value": "100",
                },
                {
                    "tx_hash": "0xdup",
                    "chain": "eth",
                    "block_timestamp": 1704067201,
                    "from_address": ADDR,
                    "to_address": "0xcc",
                    "value": "200",
                },
            ],
            user=_user(),
        )
        # "transactions" mirrors the latest ingestion batch size, while the
        # persisted count reflects the de-duplicated wallet store.
        assert out.transactions == 2
        assert out.persisted_transactions == 1


class TestCasesAPI:
    def test_create_list_get_patch_delete(self, app_client):
        resp = app_client.post(
            "/api/v1/investigations",
            json={"name": "API case", "primary_wallet": ADDR},
        )
        assert resp.status_code == 201
        case = resp.json()
        case_id = case["id"]

        listing = app_client.get("/api/v1/investigations")
        assert listing.status_code == 200
        assert listing.json()["total"] >= 1

        fetched = app_client.get(f"/api/v1/investigations/{case_id}")
        assert fetched.status_code == 200
        assert fetched.json()["id"] == case_id

        patched = app_client.patch(
            f"/api/v1/investigations/{case_id}",
            json={"status": "review", "tags": ["test"]},
        )
        assert patched.status_code == 200
        assert patched.json()["status"] == "review"

        deleted = app_client.delete(f"/api/v1/investigations/{case_id}")
        assert deleted.status_code == 200
        missing = app_client.get(f"/api/v1/investigations/{case_id}")
        assert missing.status_code == 404

    def test_create_requires_valid_wallet(self, app_client):
        resp = app_client.post(
            "/api/v1/investigations",
            json={"name": "bad", "primary_wallet": "0xzzz"},
        )
        assert resp.status_code == 422

    def test_risk_endpoint_healthy_for_empty_case(self, app_client):
        case = app_client.post(
            "/api/v1/investigations",
            json={"name": "risk case", "primary_wallet": ADDR},
        ).json()
        resp = app_client.get(f"/api/v1/investigations/{case['id']}/risk")
        assert resp.status_code == 200
        assert resp.json()["level"] in {"critical", "high", "medium", "low", "unknown"}
        assert "not a determination" in resp.json()["disclaimer"].lower()

    def test_apply_analysis_endpoint_flow(self, app_client):
        case = app_client.post(
            "/api/v1/investigations",
            json={"name": "apply case", "primary_wallet": ADDR},
        ).json()
        resp = app_client.post(
            f"/api/v1/investigations/{case['id']}/apply-analysis",
            json=ApplyAnalysisRequest(
                address=ADDR,
                analysis_id="attr-manual",
                data_source="live",
                candidates=[
                    {
                        "vasp_name": "Binance",
                        "score": 90.0,
                        "confidence": "HIGH",
                        "score_breakdown": {"known_address_match": 100},
                    }
                ],
                transactions=[
                    {
                        "tx_hash": "0x2",
                        "chain": "eth",
                        "block_timestamp": 1704067200,
                        "from_address": ADDR,
                        "to_address": "0xcc",
                        "value": "50",
                    }
                ],
            ).model_dump(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "investigating"
        assert data["vasp_candidates"] == 1
        assert data["transactions"] == 1
        assert data["risk"] in {"critical", "high", "medium", "low", "unknown"}

    def test_apply_analysis_wrong_wallet_conflict(self, app_client):
        case = app_client.post(
            "/api/v1/investigations",
            json={"name": "conflict case", "primary_wallet": ADDR},
        ).json()
        resp = app_client.post(
            f"/api/v1/investigations/{case['id']}/apply-analysis",
            json={
                "address": OTHER_ADDR,
                "analysis_id": "attr-manual",
                "data_source": "live",
            },
        )
        assert resp.status_code == 409


class TestCaseNotes:
    def test_notes_are_scoped_to_their_case(self):
        svc = _service()
        case_a = svc.create(
            InvestigationCreate(name="Alpha", primary_wallet=ADDR, network="eth"),
            _user(),
        )
        case_b = svc.create(
            InvestigationCreate(
                name="Beta", primary_wallet=OTHER_ADDR, network="eth"
            ),
            _user(),
        )

        svc.add_note(
            case_a.id,
            InvestigationNoteCreate(body="first observation", author="admin"),
            _user(),
        )
        svc.add_note(
            case_a.id,
            InvestigationNoteCreate(body="second observation", author="admin"),
            _user(),
        )

        notes_a = svc.notes(case_a.id, _user())
        notes_b = svc.notes(case_b.id, _user())
        assert [n.body for n in notes_a.notes] == [
            "first observation",
            "second observation",
        ]
        assert notes_a.total == 2
        assert notes_b.total == 0
        assert all(n.case_id == case_a.id for n in notes_a.notes)
        assert all(n.id.startswith("note-") for n in notes_a.notes)

    def test_notes_respect_ownership_scoping(self):
        svc = _service()
        case = svc.create(
            InvestigationCreate(name="Alpha", primary_wallet=ADDR, network="eth"),
            _user(uid=1),
        )
        outsider = _user(uid=99, role="investigator", username="investigator")
        with pytest.raises(CaseNotFoundError):
            svc.notes(case.id, outsider)

    def test_notes_api_flow(self, app_client):
        case = app_client.post(
            "/api/v1/investigations",
            json={"name": "notes case", "primary_wallet": ADDR},
        ).json()
        case_id = case["id"]

        empty = app_client.get(f"/api/v1/investigations/{case_id}/notes")
        assert empty.status_code == 200
        assert empty.json()["total"] == 0
        assert empty.json()["case_id"] == case_id

        created = app_client.post(
            f"/api/v1/investigations/{case_id}/notes",
            json={"body": "Trail observed", "author": "admin"},
        )
        assert created.status_code == 201
        note = created.json()
        assert note["case_id"] == case_id
        assert note["body"] == "Trail observed"
        assert note["author"] == "admin"
        assert note["id"]

        listing = app_client.get(f"/api/v1/investigations/{case_id}/notes")
        assert listing.status_code == 200
        assert listing.json()["total"] == 1
        assert listing.json()["notes"][0]["body"] == "Trail observed"

    def test_notes_api_rejects_unknown_case(self, app_client):
        resp = app_client.get("/api/v1/investigations/case-missing/notes")
        assert resp.status_code == 404
        resp = app_client.post(
            "/api/v1/investigations/case-missing/notes",
            json={"body": "x", "author": "admin"},
        )
        assert resp.status_code == 404

    def test_notes_api_rejects_empty_body(self, app_client):
        case = app_client.post(
            "/api/v1/investigations",
            json={"name": "notes case", "primary_wallet": ADDR},
        ).json()
        resp = app_client.post(
            f"/api/v1/investigations/{case['id']}/notes",
            json={"body": "", "author": "admin"},
        )
        assert resp.status_code in {400, 422}