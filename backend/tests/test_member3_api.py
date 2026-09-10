import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


class TestIntelligenceAPI:
    def test_health_still_works(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_address_intelligence_known(self, client):
        resp = client.get(
            "/api/v1/intelligence/address/0xaabb000000000000000000000000000000000001",
            params={"chain": "eth"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_known_vasp"] is True
        assert data["known_vasp"] == "SynthExchange_A"

    def test_address_intelligence_unknown(self, client):
        resp = client.get(
            "/api/v1/intelligence/address/0xunknown000000000000000000000000000000",
            params={"chain": "eth"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_known_vasp"] is False

    def test_vasp_names(self, client):
        resp = client.get("/api/v1/intelligence/vasp/names", params={"chain": "eth"})
        assert resp.status_code == 200
        data = resp.json()
        assert "SynthExchange_A" in data["vasp_names"]


class TestAttributionAPI:
    def test_analyze_known_address(self, client):
        resp = client.post(
            "/api/v1/attribution/analyze",
            json={
                "address": "0xaabb000000000000000000000000000000000001",
                "chain": "eth",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["address"] == "0xaabb000000000000000000000000000000000001"
        assert len(data["candidates"]) > 0
        assert "NOT proof" in data["disclaimer"]

    def test_analyze_unknown_address(self, client):
        resp = client.post(
            "/api/v1/attribution/analyze",
            json={"address": "0xunknown", "chain": "eth"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["candidates"]) >= 1
        for c in data["candidates"]:
            assert c["score"] == 0.0
            assert c["confidence"] == "LOW"

    def test_analyze_with_graph_data(self, client):
        resp = client.post(
            "/api/v1/attribution/analyze",
            json={
                "address": "0x1234",
                "chain": "eth",
                "graph_data": {
                    "bfs": {
                        "nodes": [
                            {
                                "wallet_id": "eth:0xaabb000000000000000000000000000000000001",
                                "chain": "eth",
                                "depth": 1,
                            }
                        ]
                    },
                    "flows": [
                        {
                            "source": "eth:0xaabb000000000000000000000000000000000001",
                            "target": "eth:0x1234",
                            "amount": "500",
                            "timestamp": 1704067200,
                        }
                    ],
                    "communities": [
                        {
                            "community_id": 1,
                            "wallets": [
                                {"wallet_id": "eth:0x1234"},
                                {
                                    "wallet_id": "eth:0xaabb000000000000000000000000000000000001"
                                },
                            ],
                        }
                    ],
                },
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["candidates"][0]["score"] > 0

    def test_get_weights(self, client):
        resp = client.get("/api/v1/attribution/weights")
        assert resp.status_code == 200
        data = resp.json()
        assert "graph_proximity" in data
        assert "known_address_match" in data
        assert "disclaimer" in data


class TestEvidenceAPI:
    def test_evidence_not_found(self, client):
        resp = client.get("/api/v1/evidence/nonexistent")
        assert resp.status_code == 404

    def test_evidence_after_attribution(self, client):
        client.post(
            "/api/v1/attribution/analyze",
            json={
                "address": "0xaabb000000000000000000000000000000000001",
                "chain": "eth",
            },
        )
        resp = client.get(
            "/api/v1/evidence/address/0xaabb000000000000000000000000000000000001",
            params={"chain": "eth"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    def test_evidence_provenance(self, client):
        client.post(
            "/api/v1/attribution/analyze",
            json={
                "address": "0xaabb000000000000000000000000000000000001",
                "chain": "eth",
            },
        )
        resp = client.get(
            "/api/v1/evidence/address/0xaabb000000000000000000000000000000000001",
            params={"chain": "eth"},
        )
        for ev in resp.json():
            assert "provenance" in ev
            assert ev["provenance"]["created_by"] == "attribution_engine"

    def test_evidence_for_attribution(self, client):
        resp = client.post(
            "/api/v1/attribution/analyze",
            json={
                "address": "0xaabb000000000000000000000000000000000001",
                "chain": "eth",
            },
        )
        attr_id = resp.json()["analysis_id"]
        resp2 = client.get(f"/api/v1/evidence/attribution/{attr_id}")
        assert resp2.status_code == 200
        assert len(resp2.json()) > 0


class TestGraphRoutesStillWork:
    def test_graph_health(self, client):
        resp = client.get("/api/v1/graph/health")
        assert resp.status_code == 200

    def test_graph_summary(self, client, monkeypatch):
        from graph import service as graph_svc

        monkeypatch.setattr(
            graph_svc,
            "build_graph",
            lambda driver: {"wallet_count": 2, "transaction_count": 5},
        )
        resp = client.get("/api/v1/graph/summary")
        assert resp.status_code == 200

    def test_root_still_works(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["project"] == "SIH26182-CryptoTrace"
