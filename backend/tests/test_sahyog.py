"""Tests for the SAHYOG referral (DEMO) flow."""

import pytest

from cases.repository import MemoryInvestigationRepository
from cases.service import InvestigationService
from sahyog.models import HandoffRequest, SahyogReferralCreate, TriageRequest
from sahyog.repository import MemorySahyogRepository
from sahyog.service import (
    SahyogChainNotSupportedError,
    SahyogReferralNotFoundError,
    SahyogService,
)

ADDR = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
BTC_ADDR = "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"


def _user():
    from app import models

    return models.User(
        id=1, username="admin", role="admin", title="t", display_name="Admin",
        password_hash="x",
    )


def _svc():
    return SahyogService(repository=MemorySahyogRepository())


def _case_svc():
    return InvestigationService(repository=MemoryInvestigationRepository())


class TestSahyogService:
    def test_ingest_creates_new_referral(self):
        svc = _svc()
        out = svc.ingest(
            SahyogReferralCreate(
                fir_no="FIR/2025/001",
                victim_name="Jane Doe",
                amount_usdt=250000.0,
                suspect_wallet=ADDR,
                chain="eth",
            )
        )
        assert out.id.startswith("sy-")
        assert out.status == "new"
        assert out.chain == "eth"
        assert out.victim_name == "Jane Doe"
        assert out.data_source == "demo"

    def test_triage_marks_triaged(self):
        svc = _svc()
        out = svc.ingest(
            SahyogReferralCreate(
                fir_no="FIR/2025/002",
                victim_name="Jane Doe",
                amount_usdt=5000000.0,
                suspect_wallet=ADDR,
            )
        )
        triaged = svc.triage(out.id, TriageRequest(), _user())
        assert triaged.status == "triaged"
        assert triaged.triage is not None
        assert triaged.triage["risk"] == "high"
        assert triaged.triage["triaged_by"] == "admin"
        assert "analysis" in triaged.triage["recommendation"].lower()

    def test_triage_low_value_recommendation(self):
        svc = _svc()
        out = svc.ingest(
            SahyogReferralCreate(
                fir_no="FIR/2025/003",
                victim_name="Jane Doe",
                amount_usdt=50.0,
                suspect_wallet=ADDR,
            )
        )
        triaged = svc.triage(out.id, TriageRequest(), _user())
        assert triaged.triage["risk"] == "low"
        assert "monitor" in triaged.triage["recommendation"].lower()

    def test_handoff_creates_case(self):
        svc = _svc()
        case_svc = _case_svc()
        out = svc.ingest(
            SahyogReferralCreate(
                fir_no="FIR/2025/004",
                victim_name="Jane Doe",
                amount_usdt=100000.0,
                suspect_wallet=ADDR,
            )
        )
        handed = svc.handoff(out.id, HandoffRequest(), _user(), case_svc)
        assert handed.status == "handed_off"
        assert handed.handoff_case_id.startswith("case-")
        case = case_svc.get(handed.handoff_case_id, _user())
        assert case.primary_wallet == ADDR
        assert case.tags == ["sahyog"]

    def test_handoff_rejects_btc(self):
        svc = _svc()
        out = svc.ingest(
            SahyogReferralCreate(
                fir_no="FIR/2025/005",
                victim_name="Jane Doe",
                amount_usdt=1000.0,
                suspect_wallet=BTC_ADDR,
                chain="btc",
            )
        )
        with pytest.raises(SahyogChainNotSupportedError):
            svc.handoff(out.id, HandoffRequest(), _user(), _case_svc())

    def test_unknown_referral_raises(self):
        svc = _svc()
        with pytest.raises(SahyogReferralNotFoundError):
            svc.get("sy-nonexistent")


class TestSahyogAPI:
    def test_full_flow(self, app_client):
        resp = app_client.post(
            "/api/v1/sahyog/referrals",
            json={
                "fir_no": "FIR/2025/API-1",
                "victim_name": "API Victim",
                "amount_usdt": 120000.0,
                "suspect_wallet": ADDR,
                "chain": "eth",
            },
        )
        assert resp.status_code == 201
        referral = resp.json()
        ref_id = referral["id"]

        listing = app_client.get("/api/v1/sahyog/referrals")
        assert listing.status_code == 200
        assert any(r["id"] == ref_id for r in listing.json())

        triaged = app_client.post(
            f"/api/v1/sahyog/referrals/{ref_id}/triage", json={}
        )
        assert triaged.status_code == 200
        assert triaged.json()["status"] == "triaged"

        handed = app_client.post(
            f"/api/v1/sahyog/referrals/{ref_id}/handoff",
            json={"case_name": "SAHYOG API handoff case", "priority": "high"},
        )
        assert handed.status_code == 200
        case_id = handed.json()["handoff_case_id"]
        assert case_id.startswith("case-")

        case = app_client.get(f"/api/v1/investigations/{case_id}")
        assert case.status_code == 200
        assert case.json()["tags"] == ["sahyog"]

    def test_handoff_btc_conflict(self, app_client):
        resp = app_client.post(
            "/api/v1/sahyog/referrals",
            json={
                "fir_no": "FIR/2025/API-2",
                "victim_name": "BTC Victim",
                "amount_usdt": 1000.0,
                "suspect_wallet": BTC_ADDR,
                "chain": "btc",
            },
        )
        ref_id = resp.json()["id"]
        handed = app_client.post(
            f"/api/v1/sahyog/referrals/{ref_id}/handoff", json={}
        )
        assert handed.status_code == 409

    def test_demo_notice(self, app_client):
        resp = app_client.get("/api/v1/sahyog/demo-notice")
        assert resp.status_code == 200
        assert resp.json()["is_demo"] is True