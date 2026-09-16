"""Tests for the Criminal / Sanctions Intelligence layer.

Contract under test:
- VASP attribution is NEVER converted into criminal-risk scoring and a
  VASP score is NEVER inflated by sanctions intelligence.
- Only an EXACT address match in the curated public directory elevates the
  overall risk level; the criminal_intelligence block stays None (i.e.
  UNKNOWN / NOT ASSESSED) for every other wallet, and is never phrased as
  "not criminal".
- The sanctions_match evidence and its provenance are persisted (source_type
  curated_public_intelligence), the assistant answers from persisted
  evidence, the PDF keeps the Criminal / Sanctions Intelligence section
  separate from VASP/risk/evidence, and the graph does NOT flag every
  connected wallet.
"""

import pytest

from app import models
from assistant.models import AssistantRequest
from assistant.service import AssistantService
from assistant.tools import AssistantTools
from cases.repository import MemoryInvestigationRepository
from cases.service import InvestigationService
from evidence.models import EvidenceRecord, EvidenceType, Provenance
from evidence.repository import EvidenceRepository
from evidence.service import EvidenceService
from intelligence.sanctions_service import (
    SanctionsIntelligenceService,
    sanctions_evidence_id,
)
from reports import models as report_models
from risk.repository import MemoryRiskRepository
from risk.service import RiskService
from wallets.repository import MemoryWalletRepository
from wallets.service import WalletService

CURATED = "0x098B716B8Aaf21512996dC57EB0615e2383E2f96"
CURATED_LOWER = "0x098b716b8aaf21512996dc57eb0615e2383e2f96"
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


def _candidate(name, score, confidence="LOW", match=0):
    return {
        "vasp_name": name,
        "score": score,
        "confidence": confidence,
        "score_breakdown": {"known_address_match": match},
    }


def _assistant_service() -> AssistantService:
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


class TestSanctionsEngine:
    def test_exact_match_elevates_level_to_high(self):
        a = RiskService(repository=MemoryRiskRepository()).evaluate(
            address=CURATED, chain="eth", candidates=[]
        )
        assert a.level == "high"
        assert a.criminal_intelligence is not None

    def test_exact_match_carries_high_confidence_curated_fields(self):
        a = RiskService(repository=MemoryRiskRepository()).evaluate(
            address=CURATED, chain="eth", candidates=[]
        )
        ci = a.criminal_intelligence or {}
        assert ci["status"] == "exact_sanctions_match"
        assert ci["entity"] == "Lazarus Group"
        assert ci["source"] == "OFAC"
        assert ci["confidence"] == "HIGH"
        assert ci["match_type"] == "exact_address"
        assert ci["source_type"] == "public_government"
        assert ci["provenance_source_type"] == "curated_public_intelligence"
        assert ci["evidence_id"] == sanctions_evidence_id(CURATED, "eth")
        assert ci["level"] == "high"
        assert "CURATED PUBLIC INTELLIGENCE" in ci["disclaimer"].upper()
        kinds = {s.name for s in a.signals}
        assert "sanctions_exact_address_match" in kinds
        assert "known_illicit_entity_attribution" in kinds

    def test_unknown_wallet_not_assessed_never_lawful_claim(self):
        a = RiskService(repository=MemoryRiskRepository()).evaluate(
            address=OTHER_ADDR, chain="eth", candidates=[]
        )
        assert a.criminal_intelligence is None
        assert a.signals == []
        assert a.level in {"unknown", "low"}
        for text in (a.summary or "") + " ".join(a.reasoning):
            assert "not criminal" not in text.lower()

    def test_vasp_score_unaltered_by_sanctions_match(self):
        sanctioned = RiskService(
            repository=MemoryRiskRepository()
        ).evaluate(
            address=CURATED,
            chain="eth",
            candidates=[_candidate("Binance", 15.5)],
        )
        plain = RiskService(repository=MemoryRiskRepository()).evaluate(
            address=OTHER_ADDR,
            chain="eth",
            candidates=[_candidate("Binance", 15.5)],
        )
        # Identical analytical scoring: the VASP number is never inflated.
        assert sanctioned.risk_score == plain.risk_score
        assert [f.label for f in sanctioned.factors] == [
            f.label for f in plain.factors
        ]
        # Only the separately-tracked block differs.
        assert sanctioned.criminal_intelligence is not None
        assert sanctioned.level == "high"
        assert plain.criminal_intelligence is None

    def test_neighbor_is_never_marked(self):
        svc = SanctionsIntelligenceService()
        assert svc.lookup(OTHER_ADDR, "eth") is None
        assert svc.lookup(CURATED, "eth") is not None
        # A wallet that merely RECEIVES txns from the sanctioned address is
        # not itself flagged with a criminal/sanctions match.
        neighbor = RiskService(repository=MemoryRiskRepository()).evaluate(
            address=OTHER_ADDR,
            chain="eth",
            candidates=[],
            transfers=[
                {
                    "chain": "eth",
                    "tx_hash": "0x1",
                    "block_timestamp": 1704067200,
                    "from_address": CURATED_LOWER,
                    "to_address": OTHER_ADDR,
                    "value": "10",
                }
            ],
        )
        assert neighbor.criminal_intelligence is None
        assert neighbor.level in {"unknown", "low", "medium"}


class TestSanctionsEvidencePersistence:
    def test_evidence_and_provenance_persisted(self, app_client):
        case = app_client.post(
            "/api/v1/investigations",
            json={
                "name": "sanctions case",
                "primary_wallet": CURATED,
                "network": "eth",
            },
        ).json()
        applied = app_client.post(
            f"/api/v1/investigations/{case['id']}/apply-analysis",
            json={
                "address": CURATED,
                "analysis_id": "attr-san-1",
                "data_source": "live",
                "candidates": [],
            },
        )
        assert applied.status_code == 200
        assert applied.json()["evidence_count"] == 1

        records = app_client.get(
            f"/api/v1/evidence/investigation/{case['id']}"
        ).json()
        assert len(records) == 1
        rec = records[0]
        assert rec["evidence_type"] == "sanctions_match"
        assert rec["address"] == CURATED_LOWER
        assert rec["source"] == "OFAC"
        assert rec["confidence"] == 0.9
        assert "Lazarus Group" in rec["description"]
        assert rec["provenance"]["method"] == "sanctions_intelligence_exact_match"
        assert (
            rec["provenance"]["source_type"] == "curated_public_intelligence"
        )
        assert rec["evidence_id"] == sanctions_evidence_id(CURATED, "eth")

    def test_apply_again_is_idempotent(self, app_client):
        case = app_client.post(
            "/api/v1/investigations",
            json={
                "name": "sanctions case 2",
                "primary_wallet": CURATED,
                "network": "eth",
            },
        ).json()
        for _ in range(2):
            app_client.post(
                f"/api/v1/investigations/{case['id']}/apply-analysis",
                json={
                    "address": CURATED,
                    "analysis_id": "attr-san-2",
                    "data_source": "live",
                    "candidates": [],
                },
            )
        records = app_client.get(
            f"/api/v1/evidence/investigation/{case['id']}"
        ).json()
        assert len(records) == 1

    def test_sanctions_endpoint_returns_curated_record(self, app_client):
        resp = app_client.get(f"/api/v1/intelligence/sanctions/address/{CURATED}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["matched"] is True
        assert body["level"] == "high"
        assert body["record"]["entity"] == "Lazarus Group"
        assert body["record"]["source"] == "OFAC"
        assert body["record"]["match_type"] == "exact_address"
        assert body["record"]["confidence"] == "HIGH"

    def test_sanctions_endpoint_unknown_wallet(self, app_client):
        resp = app_client.get(
            f"/api/v1/intelligence/sanctions/address/{OTHER_ADDR}"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["matched"] is False
        assert body["level"] == "unknown"
        assert body["record"] is None


class TestSanctionsAssistant:
    def test_assistant_answers_from_persisted_evidence(self):
        svc = _assistant_service()
        svc.tools.evidence.create_evidence(
            evidence_id=sanctions_evidence_id(CURATED, "eth"),
            attribution_id="san-test-attribution",
            evidence_type=EvidenceType.SANCTIONS_MATCH,
            address=CURATED,
            chain="eth",
            confidence=0.9,
            description="Exact address match against curated public "
                        "sanctions/illicit intelligence. Entity: Lazarus "
                        "Group. Source: OFAC.",
            source="OFAC",
            method="sanctions_intelligence_exact_match",
            source_type="curated_public_intelligence",
        )
        assessment = svc.tools.risk.evaluate(
            address=CURATED, chain="eth", candidates=[]
        )
        svc.tools.risk.persist(assessment)
        resp = svc.interact(
            AssistantRequest(
                wallet_address=CURATED,
                query="why is this wallet high risk?",
                session_id="s-san-1",
            ),
            _user(uid=1),
        )
        text = " ".join(
            [s.body or "" for s in resp.sections] + [b for s in resp.sections for b in s.bullets]
        )
        assert (
            "curated public sanctions/illicit intelligence record associated "
            "with Lazarus Group" in text
        )
        assert "The source is OFAC." in text
        assert "should be independently verified" in text
        assert "CURATED PUBLIC INTELLIGENCE" in text.upper()
        assert "not a live OFAC integration" in text

    def test_assistant_unknown_wallet_is_not_assessed(self):
        svc = _assistant_service()
        resp = svc.interact(
            AssistantRequest(
                wallet_address=OTHER_ADDR,
                query="why is this wallet high risk?",
                session_id="s-san-2",
            ),
            _user(uid=1),
        )
        text = " ".join(
            [s.body or "" for s in resp.sections] + [b for s in resp.sections for b in s.bullets]
        )
        assert (
            "No curated public sanctions/illicit intelligence match is "
            "recorded" in text
        )
        assert "UNKNOWN / NOT ASSESSED" in text
        assert "not evidence that the wallet is lawful" in text


class TestSanctionsReportSeparation:
    def test_report_section_registered_with_own_title(self):
        assert "criminal_sanctions_intelligence" in report_models.REPORT_SECTIONS
        assert (
            report_models._SECTION_TITLES["criminal_sanctions_intelligence"]
            == "Criminal / Sanctions Intelligence"
        )

    def test_report_separates_vasp_and_sanctions_content(self):
        context = {
            "metadata": {"network": "eth"},
            "case": {
                "primary_wallet": CURATED_LOWER,
                "network": "eth",
                "latest_candidates": [
                    {"vasp_name": "Binance", "score": 15.5, "confidence": "LOW"}
                ],
            },
            "criminal_intelligence": {
                "level": "high",
                "status": "exact_sanctions_match",
                "entity": "Lazarus Group",
                "source": "OFAC",
                "match_type": "exact_address",
                "confidence": "HIGH",
                "source_type": "public_government",
                "provenance_source_type": "curated_public_intelligence",
                "evidence_id": "ev-san-test",
            },
        }
        vasp = report_models.build_section_content("vasp_candidates", context)
        ci = report_models.build_section_content(
            "criminal_sanctions_intelligence", context
        )
        assert "Binance" in vasp
        assert "Lazarus Group" in ci
        assert "HIGH" in ci
        assert "CURATED PUBLIC INTELLIGENCE" in ci
        assert "not a live OFAC integration" in ci
        # VASP block never references the sanctions entity; sanctions block
        # never references the exchange.
        assert "Lazarus" not in vasp
        assert "Binance" not in ci

    def test_report_unknown_block_is_honest(self):
        context = {"metadata": {}, "case": {"primary_wallet": OTHER_ADDR}}
        ci = report_models.build_section_content(
            "criminal_sanctions_intelligence", context
        )
        assert "UNKNOWN / NOT ASSESSED" in ci
        assert "not evidence that the wallet is lawful" in ci
        assert "not a live OFAC integration" in ci

    def test_sections_endpoint_exposes_new_section(self, app_client):
        resp = app_client.get("/api/v1/reports/sections")
        assert resp.status_code == 200
        assert "criminal_sanctions_intelligence" in resp.json()["sections"]
