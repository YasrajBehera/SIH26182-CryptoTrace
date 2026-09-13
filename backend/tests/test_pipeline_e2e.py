import pytest

from attribution.models import Confidence
from graph.synthetic import generate_transactions
from pipeline.models import InvestigationRequest, InvestigationResult
from pipeline.service import InvestigationPipeline


def _transfer(**overrides):
    tx = {
        "chain": "eth",
        "transaction_hash": "0x666", 
        "block_number": 10,
        "block_timestamp": 1704067200,
        "from_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "to_address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "value": "1000000000000000000",
    }
    tx.update(overrides)
    return type("FakeTransfer", (), tx)()


class TestFullPipelineE2E:
    """End-to-end: wallet address -> synthetic ingestion -> graph -> attribution -> evidence."""

    def test_known_vasp_wallet_produces_ranked_candidates(self):
        synth_txs = generate_transactions(seed=42, count=30)
        vasp_addr = synth_txs[0].from_address

        pipeline = InvestigationPipeline()
        result = pipeline.run(
            InvestigationRequest(address=vasp_addr, chain="eth"),
            synth_txs=synth_txs,
        )

        assert isinstance(result, InvestigationResult)
        assert result.address == vasp_addr.lower()
        assert result.chain == "eth"
        assert result.transfers_ingested == 30
        assert result.graph_nodes > 0
        assert result.graph_edges > 0
        assert result.analysis_id.startswith("attr-")

    def test_ranked_candidates_sorted_by_score(self):
        synth_txs = generate_transactions(seed=42, count=30)
        addr = synth_txs[0].from_address

        pipeline = InvestigationPipeline()
        result = pipeline.run(
            InvestigationRequest(address=addr, chain="eth"),
            synth_txs=synth_txs,
        )

        scores = [c.score for c in result.candidates]
        assert scores == sorted(scores, reverse=True)

    def test_candidates_have_valid_confidence(self):
        synth_txs = generate_transactions(seed=42, count=30)
        addr = synth_txs[0].from_address

        pipeline = InvestigationPipeline()
        result = pipeline.run(
            InvestigationRequest(address=addr, chain="eth"),
            synth_txs=synth_txs,
        )

        for c in result.candidates:
            assert c.confidence in (Confidence.HIGH, Confidence.MEDIUM, Confidence.LOW)
            assert 0.0 <= c.score <= 100.0

    def test_candidates_have_score_breakdown(self):
        synth_txs = generate_transactions(seed=42, count=30)
        addr = synth_txs[0].from_address

        pipeline = InvestigationPipeline()
        result = pipeline.run(
            InvestigationRequest(address=addr, chain="eth"),
            synth_txs=synth_txs,
        )

        for c in result.candidates:
            assert 0 <= c.score_breakdown.graph_proximity <= 100
            assert 0 <= c.score_breakdown.known_address_match <= 100
            assert 0 <= c.score_breakdown.temporal_consistency <= 100
            assert 0 <= c.score_breakdown.transaction_flow <= 100
            assert 0 <= c.score_breakdown.cluster_evidence <= 100

    def test_evidence_created_for_nonzero_scores(self):
        synth_txs = generate_transactions(seed=42, count=30)
        addr = synth_txs[0].from_address

        pipeline = InvestigationPipeline()
        result = pipeline.run(
            InvestigationRequest(address=addr, chain="eth"),
            synth_txs=synth_txs,
        )

        assert result.evidence_count > 0

    def test_evidence_traceable_to_store(self):
        synth_txs = generate_transactions(seed=42, count=30)
        addr = synth_txs[0].from_address

        pipeline = InvestigationPipeline()
        result = pipeline.run(
            InvestigationRequest(address=addr, chain="eth"),
            synth_txs=synth_txs,
        )

        for candidate in result.candidates:
            for ev_id in candidate.evidence_ids:
                ev = pipeline.attribution_service.evidence_service.get_evidence(ev_id)
                assert ev is not None
                assert ev.address == addr.lower()
                assert ev.provenance.created_by == "attribution_engine"

    def test_address_intelligence_populated(self):
        synth_txs = generate_transactions(seed=42, count=30)
        addr = synth_txs[0].from_address

        pipeline = InvestigationPipeline()
        result = pipeline.run(
            InvestigationRequest(address=addr, chain="eth"),
            synth_txs=synth_txs,
        )

        assert result.address_intelligence is not None
        assert result.address_intelligence.address == addr.lower()

    def test_unknown_wallet_still_produces_result(self):
        pipeline = InvestigationPipeline()
        result = pipeline.run(
            InvestigationRequest(address="0xaaaa111122223333444455556666777788889999", chain="eth"),
            synth_txs=generate_transactions(seed=42, count=30),
        )

        assert isinstance(result, InvestigationResult)
        assert len(result.candidates) > 0
        assert result.analysis_id is not None

    def test_disclaimer_present(self):
        synth_txs = generate_transactions(seed=42, count=30)
        addr = synth_txs[0].from_address

        pipeline = InvestigationPipeline()
        result = pipeline.run(
            InvestigationRequest(address=addr, chain="eth"),
            synth_txs=synth_txs,
        )

        assert "NOT proof" in result.disclaimer

    def test_deterministic_results(self):
        synth_txs = generate_transactions(seed=42, count=30)
        addr = synth_txs[0].from_address

        p1 = InvestigationPipeline()
        r1 = p1.run(
            InvestigationRequest(address=addr, chain="eth"),
            synth_txs=synth_txs,
        )

        p2 = InvestigationPipeline()
        r2 = p2.run(
            InvestigationRequest(address=addr, chain="eth"),
            synth_txs=synth_txs,
        )

        assert len(r1.candidates) == len(r2.candidates)
        for c1, c2 in zip(r1.candidates, r2.candidates):
            assert c1.score == c2.score
            assert c1.confidence == c2.confidence
            assert c1.vasp_name == c2.vasp_name


class TestPipelineAPIEndpoint:
    def test_analyze_endpoint(self, app_client):
        resp = app_client.post(
            "/api/v1/investigations/0xaabb000000000000000000000000000000000001/analyze",
            params={"chain": "eth"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["address"] == "0xaabb000000000000000000000000000000000001"
        assert data["chain"] == "eth"
        assert data["transfers_ingested"] > 0
        assert data["graph_nodes"] > 0
        assert len(data["candidates"]) > 0
        assert data["analysis_id"].startswith("attr-")
        assert "NOT proof" in data["disclaimer"]

    def test_analyze_unknown_wallet(self, app_client):
        resp = app_client.post(
            "/api/v1/investigations/0xunknown/analyze",
            params={"chain": "eth"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["candidates"]) > 0
        assert data["evidence_count"] >= 0

    def test_analyze_evidence_retrievable_via_evidence_api(self, app_client):
        """Analyze advertises evidence_ids; the evidence endpoints MUST return them.

        Regression: the pipeline previously stored evidence in a private
        EvidenceService, so GET /api/v1/evidence/* could never resolve the ids
        returned by POST /api/v1/investigations/{address}/analyze.
        """
        resp = app_client.post(
            "/api/v1/investigations/0xaabb000000000000000000000000000000000001/analyze",
            params={"chain": "eth"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["evidence_count"] > 0
        assert len(data["candidates"]) > 0

        attr_id = data["analysis_id"]
        resp2 = app_client.get(f"/api/v1/evidence/attribution/{attr_id}")
        assert resp2.status_code == 200
        by_attr = resp2.json()
        assert len(by_attr) == data["evidence_count"]

        resp3 = app_client.get(
            "/api/v1/evidence/address/0xaabb000000000000000000000000000000000001",
            params={"chain": "eth"},
        )
        assert resp3.status_code == 200
        assert len(resp3.json()) > 0

    def test_create_investigation_contract(self, app_client):
        """The legacy stub POST /api/v1/investigations was replaced with a real
        investigation create. Verify the new contract (id + persisted fields)."""
        resp = app_client.post(
            "/api/v1/investigations",
            json={
                "name": "Legacy stub replacement case",
                "primary_wallet": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "description": "create-contract smoke",
                "network": "eth",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("case-")
        assert data["name"] == "Legacy stub replacement case"
        assert data["primary_wallet"] == "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        assert data["status"] == "open"
        assert data["risk"] == "unknown"

    def test_analyze_binds_to_case(self, app_client):
        """Full workflow: create case -> POST analyze?case_id -> evidence,
        risk and analysis metadata attached to the persisted case."""
        case = app_client.post(
            "/api/v1/investigations",
            json={
                "name": "bound analysis case",
                "primary_wallet": "0xaabb000000000000000000000000000000000001",
            },
        ).json()
        resp = app_client.post(
            "/api/v1/investigations/0xaabb000000000000000000000000000000000001/analyze",
            params={"chain": "eth", "case_id": case["id"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["case_id"] == case["id"]
        assert data["data_source"] == "demo"

        updated = app_client.get(f"/api/v1/investigations/{case['id']}")
        assert updated.status_code == 200
        body = updated.json()
        assert body["status"] == "investigating"
        assert body["evidence_count"] > 0
        assert body["risk"] in {"critical", "high", "medium", "low", "unknown"}
        assert body["latest_analysis_id"].startswith("attr-")

        evidence = app_client.get(
            f"/api/v1/evidence/investigation/{case['id']}"
        )
        assert evidence.status_code == 200
        assert len(evidence.json()) == body["evidence_count"]
        for ev in evidence.json():
            assert ev["investigation_id"] == case["id"]

    def test_analyze_with_case_id_mismatched_wallet_conflicts(self, app_client):
        case = app_client.post(
            "/api/v1/investigations",
            json={
                "name": "mismatch case",
                "primary_wallet": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            },
        ).json()
        resp = app_client.post(
            "/api/v1/investigations/0xaabb000000000000000000000000000000000001/analyze",
            params={"chain": "eth", "case_id": case["id"]},
        )
        assert resp.status_code == 409

    def test_health_still_works(self, app_client):
        resp = app_client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_root_still_works(self, app_client):
        resp = app_client.get("/")
        assert resp.status_code == 200
        assert resp.json()["project"] == "SIH26182-CryptoTrace"


class TestPipelineNeo4jSync:
    """LIVE analyses mirror ingested rows into Neo4j; demo/synthetic never do."""

    def test_live_pipeline_syncs_to_neo4j(self, monkeypatch):
        synth_txs = generate_transactions(seed=42, count=30)
        pipeline = InvestigationPipeline(sync_to_neo4j=True)
        pipeline._try_live = lambda request: (
            [synth_txs[0], synth_txs[1]],
            "live",
        )
        calls = []
        pipeline._sync_live_to_neo4j = lambda rows: calls.append(len(rows)) or 2

        result = pipeline.run(
            InvestigationRequest(address=synth_txs[0].from_address, chain="eth")
        )

        assert result.data_source == "live"
        assert calls == [2]

    def test_demo_pipeline_never_syncs(self, monkeypatch):
        pipeline = InvestigationPipeline(sync_to_neo4j=True)
        pipeline._sync_live_to_neo4j = lambda rows: (_ for _ in ()).throw(
            AssertionError("demo path must not touch Neo4j")
        )
        result = pipeline.run(
            InvestigationRequest(address="0xaaaa000000000000000000000000000000000001", chain="eth"),
            synth_txs=generate_transactions(seed=42, count=30),
        )
        assert result.data_source == "demo"
