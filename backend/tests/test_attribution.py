import pytest

from attribution.models import (
    AttributionCandidate,
    AttributionRequest,
    AttributionResponse,
    Confidence,
    ScoreBreakdown,
)
from attribution.scoring import AttributionScorer, ScoringWeights
from attribution.service import AttributionService
from evidence.service import EvidenceService
from intelligence.service import VASPIntelligenceService


@pytest.fixture
def intel_service():
    return VASPIntelligenceService()


@pytest.fixture
def evidence_service():
    return EvidenceService()


@pytest.fixture
def scorer(intel_service, evidence_service):
    return AttributionScorer(
        vasp_repo=intel_service.repository,
        evidence_svc=evidence_service,
    )


@pytest.fixture
def attr_service(intel_service, evidence_service):
    return AttributionService(
        vasp_intelligence=intel_service,
        evidence_service=evidence_service,
    )


class TestScoringWeights:
    def test_default_weights(self):
        w = ScoringWeights()
        assert w.graph_proximity == 0.25
        assert w.known_address_match == 0.35
        assert w.temporal_consistency == 0.15
        assert w.transaction_flow == 0.15
        assert w.cluster_evidence == 0.10

    def test_normalized_weights(self):
        w = ScoringWeights(
            graph_proximity=0.5,
            known_address_match=0.5,
            temporal_consistency=0.0,
            transaction_flow=0.0,
            cluster_evidence=0.0,
        )
        norm = w.normalized()
        assert abs(norm.graph_proximity - 0.5) < 1e-9
        assert abs(norm.known_address_match - 0.5) < 1e-9
        assert norm.temporal_consistency == 0.0

    def test_zero_weights_stay_zero(self):
        w = ScoringWeights(
            graph_proximity=0,
            known_address_match=0,
            temporal_consistency=0,
            transaction_flow=0,
            cluster_evidence=0,
        )
        norm = w.normalized()
        assert norm.graph_proximity == 0.0


class TestScoreGraphProximity:
    def test_direct_neighbor_known_vasp(self, scorer):
        score, explanations = scorer.score_graph_proximity(
            "0x1234",
            "eth",
            neighbor_wallet_ids=["eth:0xaabb000000000000000000000000000000000001"],
        )
        assert score == 100.0
        assert len(explanations) > 0

    def test_no_vasp_neighbor(self, scorer):
        score, _ = scorer.score_graph_proximity(
            "0x1234",
            "eth",
            neighbor_wallet_ids=["eth:0xunknown000000000000000000000000000000000"],
        )
        assert score == 5.0

    def test_no_neighbors(self, scorer):
        score, explanations = scorer.score_graph_proximity(
            "0x1234", "eth", neighbor_wallet_ids=[]
        )
        assert score == 0.0

    def test_path_to_known_vasp(self, scorer):
        path_data = {
            "found": True,
            "path": [
                "eth:0x1234",
                "eth:0xunknown",
                "eth:0xaabb000000000000000000000000000000000001",
            ],
        }
        score, _ = scorer.score_graph_proximity(
            "0x1234", "eth", neighbor_wallet_ids=[], path_data=path_data
        )
        assert score >= 50.0


class TestScoreKnownAddressMatch:
    def test_direct_match(self, scorer):
        score, explanations = scorer.score_known_address_match(
            "0xaabb000000000000000000000000000000000001", "eth"
        )
        assert score == 95.0
        assert "SynthExchange_A" in explanations[0]

    def test_no_match(self, scorer):
        score, explanations = scorer.score_known_address_match(
            "0xunknown", "eth"
        )
        assert score == 0.0
        assert "not found" in explanations[0].lower()

    def test_disputed_match(self, scorer):
        score, _ = scorer.score_known_address_match(
            "0xdead00000000000000000000000000000000000d", "eth"
        )
        assert score == 25.0


class TestScoreTemporalConsistency:
    def test_no_data(self, scorer):
        score, _ = scorer.score_temporal_consistency("0x1", "eth", None)
        assert score == 0.0

    def test_no_flows(self, scorer):
        score, _ = scorer.score_temporal_consistency("0x1", "eth", {})
        assert score == 0.0

    def test_insufficient_timestamps(self, scorer):
        graph_data = {"flows": [{"timestamp": 1000}]}
        score, explanations = scorer.score_temporal_consistency(
            "0x1", "eth", graph_data
        )
        assert score == 20.0

    def test_regular_intervals(self, scorer):
        graph_data = {
            "flows": [
                {"timestamp": 1000},
                {"timestamp": 1060},
                {"timestamp": 1120},
                {"timestamp": 1180},
                {"timestamp": 1240},
            ]
        }
        score, explanations = scorer.score_temporal_consistency(
            "0x1", "eth", graph_data
        )
        assert score >= 60.0

    def test_highly_irregular(self, scorer):
        graph_data = {
            "flows": [
                {"timestamp": 1000},
                {"timestamp": 1001},
                {"timestamp": 50000},
                {"timestamp": 50010},
                {"timestamp": 999999},
            ]
        }
        score, explanations = scorer.score_temporal_consistency(
            "0x1", "eth", graph_data
        )
        assert score <= 20.0


class TestScoreTransactionFlow:
    def test_no_data(self, scorer):
        score, _ = scorer.score_transaction_flow("0x1", "eth", None)
        assert score == 0.0

    def test_many_counterparties(self, scorer):
        wallet_id = "eth:0x1234"
        neighbors = [{"wallet_id": f"eth:0x{i:040x}"} for i in range(25)]
        flows = [
            {"source": f"eth:0x{i:040x}", "target": wallet_id, "amount": "100"}
            for i in range(25)
        ]
        graph_data = {"neighbors": neighbors, "flows": flows}
        score, _ = scorer.score_transaction_flow("0x1234", "eth", graph_data)
        assert score >= 70.0

    def test_few_counterparties(self, scorer):
        wallet_id = "eth:0x1234"
        neighbors = [{"wallet_id": "eth:0x01"}, {"wallet_id": "eth:0x02"}]
        flows = [
            {"source": "eth:0x01", "target": wallet_id, "amount": "100"},
            {"source": wallet_id, "target": "eth:0x02", "amount": "50"},
        ]
        graph_data = {"neighbors": neighbors, "flows": flows}
        score, _ = scorer.score_transaction_flow("0x1234", "eth", graph_data)
        assert score <= 30.0


class TestScoreClusterEvidence:
    def test_no_data(self, scorer):
        score, _ = scorer.score_cluster_evidence("0x1", "eth", None)
        assert score == 0.0

    def test_in_cluster_with_known_vasp(self, scorer):
        graph_data = {
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
            ]
        }
        score, explanations = scorer.score_cluster_evidence(
            "0x1234", "eth", graph_data
        )
        assert score >= 50.0

    def test_in_cluster_no_vasp(self, scorer):
        graph_data = {
            "communities": [
                {
                    "community_id": 1,
                    "wallets": [
                        {"wallet_id": "eth:0x1234"},
                        {"wallet_id": "eth:0x0001"},
                    ],
                }
            ]
        }
        score, explanations = scorer.score_cluster_evidence(
            "0x1234", "eth", graph_data
        )
        assert score == 15.0

    def test_not_in_any_cluster(self, scorer):
        graph_data = {
            "communities": [
                {
                    "community_id": 1,
                    "wallets": [{"wallet_id": "eth:0x9999"}],
                }
            ]
        }
        score, _ = scorer.score_cluster_evidence("0x1234", "eth", graph_data)
        assert score == 0.0


class TestAttributionService:
    def test_analyze_known_address(self, attr_service):
        request = AttributionRequest(
            address="0xaabb000000000000000000000000000000000001",
            chain="eth",
        )
        response = attr_service.analyze(request)
        assert isinstance(response, AttributionResponse)
        assert response.address == "0xaabb000000000000000000000000000000000001"
        assert len(response.candidates) > 0
        assert response.analysis_id.startswith("attr-")
        assert response.timestamp is not None
        assert "NOT proof" in response.disclaimer

    def test_analyze_known_address_top_candidate(self, attr_service):
        request = AttributionRequest(
            address="0xaabb000000000000000000000000000000000001",
            chain="eth",
        )
        response = attr_service.analyze(request)
        scores = [c.score for c in response.candidates]
        assert scores == sorted(scores, reverse=True), "Candidates should be sorted by score"

    def test_analyze_unknown_address(self, attr_service):
        request = AttributionRequest(
            address="0xunknown000000000000000000000000000000000000",
            chain="eth",
        )
        response = attr_service.analyze(request)
        assert len(response.candidates) >= 1
        for c in response.candidates:
            assert c.score == 0.0
            assert c.confidence == Confidence.LOW

    def test_analyze_with_graph_data(self, attr_service):
        graph_data = {
            "bfs": {
                "nodes": [
                    {
                        "wallet_id": "eth:0xaabb000000000000000000000000000000000001",
                        "address": "0xaabb000000000000000000000000000000000001",
                        "chain": "eth",
                        "depth": 1,
                    }
                ]
            },
            "flows": [
                {
                    "source": "eth:0xaabb000000000000000000000000000000000001",
                    "target": "eth:0x1234",
                    "amount": "1000",
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
        }
        request = AttributionRequest(
            address="0x1234",
            chain="eth",
            graph_data=graph_data,
        )
        response = attr_service.analyze(request)
        top = response.candidates[0]
        assert top.score > 0.0
        assert len(top.evidence_ids) > 0

    def test_confidence_levels(self, attr_service):
        request = AttributionRequest(
            address="0xaabb000000000000000000000000000000000001",
            chain="eth",
        )
        response = attr_service.analyze(request)
        for candidate in response.candidates:
            assert candidate.confidence in (Confidence.HIGH, Confidence.MEDIUM, Confidence.LOW)

    def test_score_breakdown_present(self, attr_service):
        request = AttributionRequest(
            address="0xaabb000000000000000000000000000000000001",
            chain="eth",
        )
        response = attr_service.analyze(request)
        for candidate in response.candidates:
            assert isinstance(candidate.score_breakdown, ScoreBreakdown)
            assert 0 <= candidate.score_breakdown.graph_proximity <= 100
            assert 0 <= candidate.score_breakdown.known_address_match <= 100

    def test_evidence_stored(self, attr_service):
        request = AttributionRequest(
            address="0xaabb000000000000000000000000000000000001",
            chain="eth",
        )
        response = attr_service.analyze(request)
        for candidate in response.candidates:
            for ev_id in candidate.evidence_ids:
                ev = attr_service.evidence_service.get_evidence(ev_id)
                assert ev is not None
                assert ev.address == "0xaabb000000000000000000000000000000000001"

    def test_deterministic_scoring(self):
        svc1 = AttributionService()
        svc2 = AttributionService()
        req = AttributionRequest(
            address="0xccdd000000000000000000000000000000000003",
            chain="eth",
        )
        r1 = svc1.analyze(req)
        r2 = svc2.analyze(req)
        assert len(r1.candidates) == len(r2.candidates)
        for c1, c2 in zip(r1.candidates, r2.candidates):
            assert c1.score == c2.score
            assert c1.confidence == c2.confidence
            assert c1.vasp_name == c2.vasp_name

    def test_score_0_to_100_range(self, attr_service):
        request = AttributionRequest(
            address="0xaabb000000000000000000000000000000000001",
            chain="eth",
        )
        response = attr_service.analyze(request)
        for candidate in response.candidates:
            assert 0.0 <= candidate.score <= 100.0


class TestConfidenceThresholds:
    def test_high_threshold(self):
        assert AttributionScorer.HIGH_THRESHOLD == 70.0
        assert AttributionScorer.MEDIUM_THRESHOLD == 40.0

    def test_confidence_assignment(self, attr_service):
        svc = attr_service
        assert svc._determine_confidence(85.0) == Confidence.HIGH
        assert svc._determine_confidence(70.0) == Confidence.HIGH
        assert svc._determine_confidence(55.0) == Confidence.MEDIUM
        assert svc._determine_confidence(40.0) == Confidence.MEDIUM
        assert svc._determine_confidence(20.0) == Confidence.LOW
        assert svc._determine_confidence(0.0) == Confidence.LOW


class TestCandidateFiltering:
    """The analyze pipeline filters candidates to real signals: candidates
    that score 0.0 are dropped and replaced by a single explicit UNKNOWN
    placeholder instead of a wall of meaningless zero-score rows."""

    def test_zero_score_candidates_are_filtered_to_placeholder(self, attr_service):
        request = AttributionRequest(
            address="0xunknown000000000000000000000000000000000000",
            chain="eth",
        )
        response = attr_service.analyze(request)
        assert len(response.candidates) == 1
        placeholder = response.candidates[0]
        assert placeholder.vasp_name == "UNKNOWN"
        assert placeholder.score == 0.0
        assert placeholder.confidence == Confidence.LOW
        assert placeholder.evidence_ids == []
        assert "No VASP candidates found" in " ".join(placeholder.explanation)

    def test_positive_score_candidates_survive_filter(self, attr_service):
        request = AttributionRequest(
            address="0xaabb000000000000000000000000000000000001",
            chain="eth",
        )
        response = attr_service.analyze(request)
        assert len(response.candidates) > 0
        assert all(c.score > 0.0 for c in response.candidates)
        assert all(c.vasp_name != "UNKNOWN" for c in response.candidates)

    def test_filtered_output_stays_sorted_descending(self, attr_service):
        request = AttributionRequest(
            address="0xaabb000000000000000000000000000000000001",
            chain="eth",
        )
        response = attr_service.analyze(request)
        scores = [c.score for c in response.candidates]
        assert scores == sorted(scores, reverse=True)


class TestLiveAttribution:
    def test_live_analysis_against_curated_public_directory(self, attr_service):
        request = AttributionRequest(
            address="0x71660c4005BA85c37ccec55d0C4493E66Fe775d3",
            chain="eth",
        )
        response = attr_service.analyze(request, data_source="live")
        names = [c.vasp_name for c in response.candidates]
        assert "Coinbase" in names

    def test_live_evidence_is_flagged_as_chain_not_synthetic(self, attr_service):
        request = AttributionRequest(
            address="0x71660c4005BA85c37ccec55d0C4493E66Fe775d3",
            chain="eth",
        )
        response = attr_service.analyze(request, data_source="live")
        assert any(c.vasp_name == "Coinbase" and c.evidence_ids for c in response.candidates)
        for candidate in response.candidates:
            for ev_id in candidate.evidence_ids:
                ev = attr_service.evidence_service.get_evidence(ev_id)
                assert ev is not None
                assert ev.source == "chain"

    def test_demo_evidence_remains_synthetic(self, attr_service):
        request = AttributionRequest(
            address="0xaabb000000000000000000000000000000000001",
            chain="eth",
        )
        response = attr_service.analyze(request, data_source="demo")
        assert response.candidates
        for candidate in response.candidates:
            for ev_id in candidate.evidence_ids:
                ev = attr_service.evidence_service.get_evidence(ev_id)
                assert ev is not None
                assert ev.source == "synthetic"
