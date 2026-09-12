"""Tests for the analytical risk assessment module."""

from risk.repository import MemoryRiskRepository
from risk.service import RiskService

ADDR = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def _candidate(name, score, confidence="LOW", match=0):
    return {
        "vasp_name": name,
        "score": score,
        "confidence": confidence,
        "score_breakdown": {"known_address_match": match},
    }


class TestRiskService:
    def setup_method(self):
        self.svc = RiskService(repository=MemoryRiskRepository())

    def test_unknown_wallet_low_risk(self):
        a = self.svc.evaluate(
            address=ADDR, chain="eth", candidates=[_candidate("Binance", 5.0)]
        )
        assert a.level == "unknown"
        assert 0 <= a.risk_score <= 100
        assert "not a determination" in a.disclaimer.lower()

    def test_high_candidate_raises_level(self):
        a = self.svc.evaluate(
            address=ADDR,
            chain="eth",
            candidates=[_candidate("Binance", 95.0, "HIGH", match=100)],
        )
        assert a.level in {"critical", "high"}

    def test_persist_and_retrieve_by_investigation(self):
        a = self.svc.evaluate(
            address=ADDR,
            chain="eth",
            candidates=[_candidate("Binance", 70.0)],
            investigation_id="case-1",
        )
        self.svc.persist(a)
        got = self.svc.get_for_investigation("case-1")
        assert got is not None
        assert got.level == a.level
        assert got.risk_score == a.risk_score

    def test_transfers_contribute_counterparty_signal(self):
        transfers = [
            {
                "chain": "eth",
                "tx_hash": f"0x{i}",
                "block_timestamp": 1704067200 + i,
                "from_address": f"0x{99-i:02x}",
                "to_address": ADDR,
                "value": "10",
            }
            for i in range(30)
        ]
        a = self.svc.evaluate(
            address=ADDR,
            chain="eth",
            candidates=[_candidate("Binance", 40.0)],
            transfers=transfers,
        )
        assert any(f.label == "counterparty_exposure" for f in a.factors)

    def test_level_thresholds(self):
        assert self.svc._level_for(90) == "critical"
        assert self.svc._level_for(70) == "high"
        assert self.svc._level_for(50) == "medium"
        assert self.svc._level_for(20) == "low"
        assert self.svc._level_for(5) == "unknown"

    def test_persist_and_retrieve_by_wallet(self):
        a = self.svc.evaluate(
            address=ADDR, chain="eth", candidates=[_candidate("Binance", 88.0)]
        )
        self.svc.persist(a)
        got = self.svc.get_for_wallet(ADDR, "eth")
        assert got is not None
        assert got.level in {"critical", "high"}


class TestRiskAPI:
    def test_wallet_risk_404_without_data(self, app_client):
        resp = app_client.get(f"/api/v1/risk/wallet/{ADDR}")
        assert resp.status_code == 404

    def test_wallet_risk_available_after_assessment(self, app_client):
        case = app_client.post(
            "/api/v1/investigations",
            json={"name": "risk api case", "primary_wallet": ADDR},
        ).json()
        app_client.post(
            f"/api/v1/investigations/{case['id']}/apply-analysis",
            json={
                "address": ADDR,
                "analysis_id": "attr-risk-1",
                "data_source": "live",
                "candidates": [_candidate("Binance", 92.0, "HIGH", match=100)],
            },
        )
        resp = app_client.get(f"/api/v1/risk/wallet/{ADDR}")
        assert resp.status_code == 200
        assert resp.json()["level"] in {"critical", "high"}