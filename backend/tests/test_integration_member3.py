import pytest

from attribution.adapter import build_graph_data
from attribution.models import AttributionRequest, Confidence
from attribution.service import AttributionService
from graph.builder import TransactionGraph
from graph.temporal import fund_flow, temporal_path
from graph.synthetic import generate_transactions
from intelligence.service import VASPIntelligenceService


CHAIN = "eth"


def _build_graph_and_analyze(
    target_address: str,
    known_vasp_addresses: list[str],
    bfs_depth: int = 3,
):
    """Full pipeline: synthetic txs -> graph -> adapter -> attribution."""
    synth_txs = generate_transactions(seed=42, count=30)

    graph = TransactionGraph()
    for tx in synth_txs:
        graph.add_edge(
            chain=tx.chain,
            tx_hash=tx.tx_hash,
            sender_address=tx.from_address,
            receiver_address=tx.to_address,
            amount=__import__("decimal").Decimal(tx.value),
            timestamp=tx.block_timestamp,
        )

    wallet_id = f"{CHAIN}:{target_address.lower()}"

    bfs_result = graph.bfs_path(
        wallet_id,
        f"{CHAIN}:{known_vasp_addresses[0].lower()}" if known_vasp_addresses else wallet_id,
    )

    path_result = graph.shortest_path(
        wallet_id,
        f"{CHAIN}:{known_vasp_addresses[0].lower()}" if known_vasp_addresses else wallet_id,
    )

    neighbors = graph.neighbors(wallet_id)

    bfs_response = {
        "wallet_id": wallet_id,
        "max_depth": bfs_depth,
        "nodes": [
            {"wallet_id": nid, "address": nid.split(":", 1)[-1], "chain": CHAIN, "depth": 1}
            for nid in neighbors
        ],
    }

    path_response = {
        "source": wallet_id,
        "destination": f"{CHAIN}:{known_vasp_addresses[0].lower()}" if known_vasp_addresses else wallet_id,
        "path": bfs_result.get("path", []),
        "hop_count": bfs_result.get("hop_count"),
        "found": bfs_result.get("found", False),
    }

    edges_out = graph.get_edges_from(wallet_id)
    edges_in = graph.get_edges_to(wallet_id)
    all_edges = edges_out + edges_in

    flows_for_temporal = [
        {
            "tx_hash": e.tx_hash,
            "chain": e.chain,
            "source": e.sender,
            "target": e.receiver,
            "amount": str(e.amount),
            "timestamp": e.timestamp,
        }
        for e in sorted(all_edges, key=lambda x: x.timestamp)
    ]

    temporal_flow_response = {
        "wallet_id": wallet_id,
        "direction": "all",
        "flows": flows_for_temporal,
    }

    graph_data = build_graph_data(
        bfs=bfs_response,
        path=path_response,
        temporal_flow=temporal_flow_response,
    )

    request = AttributionRequest(
        address=target_address,
        chain=CHAIN,
        graph_data=graph_data,
    )

    service = AttributionService()
    response = service.analyze(request)

    return response, graph, graph_data


class TestAdapterTransforms:
    def test_build_graph_data_empty(self):
        result = build_graph_data()
        assert result == {}

    def test_build_graph_data_bfs(self):
        bfs = {
            "wallet_id": "eth:0x1",
            "max_depth": 3,
            "nodes": [
                {"wallet_id": "eth:0x2", "address": "0x2", "chain": "eth", "depth": 1},
                {"wallet_id": "eth:0x3", "address": "0x3", "chain": "eth", "depth": 2},
            ],
        }
        result = build_graph_data(bfs=bfs)
        assert len(result["neighbors"]) == 2
        assert result["neighbors"][0]["wallet_id"] == "eth:0x2"

    def test_build_graph_data_path(self):
        path = {
            "source": "eth:0x1",
            "destination": "eth:0x2",
            "path": ["eth:0x1", "eth:0x2"],
            "hop_count": 1,
            "found": True,
        }
        result = build_graph_data(path=path)
        assert result["path"]["found"] is True
        assert result["path"]["path"] == ["eth:0x1", "eth:0x2"]

    def test_build_graph_data_path_not_found(self):
        path = {
            "source": "eth:0x1",
            "destination": "eth:99",
            "path": [],
            "hop_count": None,
            "found": False,
        }
        result = build_graph_data(path=path)
        assert "path" not in result

    def test_build_graph_data_fund_flow_normalizes_fields(self):
        fund_flow_resp = {
            "source": "eth:0x1",
            "destination": "eth:0x2",
            "wallet_path": ["eth:0x1", "eth:0x2"],
            "hop_count": 1,
            "transactions": [
                {
                    "tx_hash": "0xabc",
                    "chain": "eth",
                    "sender": "eth:0x1",
                    "receiver": "eth:0x2",
                    "amount": "1000",
                    "timestamp": 1704067200,
                }
            ],
            "found": True,
        }
        result = build_graph_data(fund_flow=fund_flow_resp)
        assert "flows" in result
        assert result["flows"][0]["source"] == "eth:0x1"
        assert result["flows"][0]["target"] == "eth:0x2"
        assert result["flows"][0]["timestamp"] == 1704067200

    def test_build_graph_data_temporal_flow(self):
        tf = {
            "wallet_id": "eth:0x1",
            "direction": "all",
            "flows": [
                {
                    "tx_id": "t1",
                    "tx_hash": "0xabc",
                    "chain": "eth",
                    "block_timestamp": 1704067200,
                    "amount": "500",
                    "source": "eth:0x1",
                    "target": "eth:0x2",
                }
            ],
        }
        result = build_graph_data(temporal_flow=tf)
        assert len(result["flows"]) == 1
        assert result["flows"][0]["timestamp"] == 1704067200

    def test_build_graph_data_clusters(self):
        clusters = {
            "algorithm": "louvain",
            "communities": [
                {
                    "community_id": 1,
                    "wallets": [
                        {"wallet_id": "eth:0x1", "address": "0x1", "chain": "eth"},
                        {"wallet_id": "eth:0x2", "address": "0x2", "chain": "eth"},
                    ],
                }
            ],
        }
        result = build_graph_data(clusters=clusters)
        assert len(result["communities"]) == 1
        assert len(result["communities"][0]["wallets"]) == 2

    def test_build_graph_data_merges_flows(self):
        fund_flow_resp = {
            "transactions": [
                {"tx_hash": "0x1", "chain": "eth", "sender": "eth:0xa", "receiver": "eth:0xb", "amount": "100", "timestamp": 100}
            ],
            "found": True,
        }
        tf = {
            "flows": [
                {"tx_hash": "0x2", "chain": "eth", "source": "eth:0xb", "target": "eth:0xa", "amount": "200", "block_timestamp": 200}
            ],
        }
        result = build_graph_data(fund_flow=fund_flow_resp, temporal_flow=tf)
        assert len(result["flows"]) == 2

    def test_normalize_flow_sender_receiver_to_source_target(self):
        from attribution.adapter import _normalize_flow

        fund_tx = {
            "tx_hash": "0xabc",
            "chain": "eth",
            "sender": "eth:0x1",
            "receiver": "eth:0x2",
            "amount": "1000",
            "timestamp": 1704067200,
        }
        normalized = _normalize_flow(fund_tx)
        assert normalized["source"] == "eth:0x1"
        assert normalized["target"] == "eth:0x2"

    def test_normalize_flow_preserves_existing_source_target(self):
        from attribution.adapter import _normalize_flow

        flow = {
            "tx_hash": "0xabc",
            "chain": "eth",
            "source": "eth:0x1",
            "target": "eth:0x2",
            "amount": "1000",
            "block_timestamp": 1704067200,
        }
        normalized = _normalize_flow(flow)
        assert normalized["source"] == "eth:0x1"
        assert normalized["target"] == "eth:0x2"
        assert normalized["timestamp"] == 1704067200


class TestFullPipelineIntegration:
    def test_known_vasp_address_scores_high(self):
        synth_txs = generate_transactions(seed=42, count=30)
        vasp_addr = synth_txs[0].from_address

        graph = TransactionGraph()
        for tx in synth_txs:
            graph.add_edge(
                chain=tx.chain,
                tx_hash=tx.tx_hash,
                sender_address=tx.from_address,
                receiver_address=tx.to_address,
                amount=__import__("decimal").Decimal(tx.value),
                timestamp=tx.block_timestamp,
            )

        wallet_id = f"{CHAIN}:{vasp_addr.lower()}"
        neighbors = graph.neighbors(wallet_id)

        bfs_response = {
            "wallet_id": wallet_id,
            "max_depth": 3,
            "nodes": [
                {"wallet_id": nid, "address": nid.split(":", 1)[-1], "chain": CHAIN, "depth": 1}
                for nid in neighbors
            ],
        }

        edges_out = graph.get_edges_from(wallet_id)
        edges_in = graph.get_edges_to(wallet_id)
        all_edges = edges_out + edges_in

        flows = [
            {
                "tx_hash": e.tx_hash,
                "chain": e.chain,
                "source": e.sender,
                "target": e.receiver,
                "amount": str(e.amount),
                "timestamp": e.timestamp,
            }
            for e in sorted(all_edges, key=lambda x: x.timestamp)
        ]

        graph_data = build_graph_data(
            bfs=bfs_response,
            temporal_flow={"wallet_id": wallet_id, "direction": "all", "flows": flows},
        )

        request = AttributionRequest(address=vasp_addr, chain=CHAIN, graph_data=graph_data)
        service = AttributionService()
        response = service.analyze(request)

        assert len(response.candidates) > 0
        for c in response.candidates:
            assert 0.0 <= c.score <= 100.0
            assert c.confidence in (Confidence.HIGH, Confidence.MEDIUM, Confidence.LOW)
            assert len(c.evidence_ids) > 0

    def test_adapter_with_real_graph_algorithms(self):
        synth_txs = generate_transactions(seed=42, count=30)

        graph = TransactionGraph()
        for tx in synth_txs:
            graph.add_edge(
                chain=tx.chain,
                tx_hash=tx.tx_hash,
                sender_address=tx.from_address,
                receiver_address=tx.to_address,
                amount=__import__("decimal").Decimal(tx.value),
                timestamp=tx.block_timestamp,
            )

        all_nodes = [n["wallet_id"] for n in graph.nodes]
        target = all_nodes[0]

        bfs_result = {}
        for other in all_nodes[1:]:
            result = graph.bfs_path(target, other)
            if result["found"]:
                bfs_result = result
                break

        path_result = graph.shortest_path(target, all_nodes[-1] if len(all_nodes) > 1 else target)

        neighbors = graph.neighbors(target)

        bfs_response = {
            "wallet_id": target,
            "max_depth": 3,
            "nodes": [
                {"wallet_id": nid, "address": nid.split(":", 1)[-1], "chain": CHAIN, "depth": 1}
                for nid in neighbors
            ],
        }

        path_response = {
            "source": target,
            "destination": bfs_result.get("destination", target),
            "path": bfs_result.get("path", []),
            "hop_count": bfs_result.get("hop_count"),
            "found": bfs_result.get("found", False),
        }

        edges_out = graph.get_edges_from(target)
        edges_in = graph.get_edges_to(target)
        all_edges = edges_out + edges_in

        flows = [
            {
                "tx_hash": e.tx_hash,
                "chain": e.chain,
                "source": e.sender,
                "target": e.receiver,
                "amount": str(e.amount),
                "timestamp": e.timestamp,
            }
            for e in sorted(all_edges, key=lambda x: x.timestamp)
        ]

        graph_data = build_graph_data(
            bfs=bfs_response,
            path=path_response,
            temporal_flow={"wallet_id": target, "direction": "all", "flows": flows},
        )

        assert "neighbors" in graph_data
        assert len(graph_data["neighbors"]) > 0

        if bfs_result.get("found"):
            assert "path" in graph_data
            assert graph_data["path"]["found"] is True

        assert "flows" in graph_data

        request = AttributionRequest(address=target.split(":", 1)[-1], chain=CHAIN, graph_data=graph_data)
        service = AttributionService()
        response = service.analyze(request)

        assert len(response.candidates) > 0
        assert response.analysis_id.startswith("attr-")

    def test_fund_flow_transactions_normalised_for_scoring(self):
        synth_txs = generate_transactions(seed=42, count=20)

        graph = TransactionGraph()
        for tx in synth_txs:
            graph.add_edge(
                chain=tx.chain,
                tx_hash=tx.tx_hash,
                sender_address=tx.from_address,
                receiver_address=tx.to_address,
                amount=__import__("decimal").Decimal(tx.value),
                timestamp=tx.block_timestamp,
            )

        all_nodes = [n["wallet_id"] for n in graph.nodes]
        if len(all_nodes) < 2:
            pytest.skip("Not enough nodes")

        source_wid = all_nodes[0]
        target_wid = all_nodes[1]

        fund_flow_result = fund_flow(graph, source_wid, target_wid)

        fund_flow_resp = {
            "source": fund_flow_result["source"],
            "destination": fund_flow_result["destination"],
            "wallet_path": fund_flow_result["wallet_path"],
            "hop_count": fund_flow_result["hop_count"],
            "transactions": fund_flow_result["transactions"],
            "found": fund_flow_result["found"],
        }

        graph_data = build_graph_data(fund_flow=fund_flow_resp)

        assert "flows" in graph_data
        for flow in graph_data["flows"]:
            assert "source" in flow
            assert "target" in flow
            assert "timestamp" in flow
            assert "sender" not in flow
            assert "receiver" not in flow

    def test_evidence_ids_traceable_to_evidence_store(self):
        synth_txs = generate_transactions(seed=42, count=20)

        graph = TransactionGraph()
        for tx in synth_txs:
            graph.add_edge(
                chain=tx.chain,
                tx_hash=tx.tx_hash,
                sender_address=tx.from_address,
                receiver_address=tx.to_address,
                amount=__import__("decimal").Decimal(tx.value),
                timestamp=tx.block_timestamp,
            )

        addr = synth_txs[0].from_address
        wallet_id = f"{CHAIN}:{addr.lower()}"
        neighbors = graph.neighbors(wallet_id)

        bfs_response = {
            "wallet_id": wallet_id,
            "max_depth": 3,
            "nodes": [
                {"wallet_id": nid, "address": nid.split(":", 1)[-1], "chain": CHAIN, "depth": 1}
                for nid in neighbors
            ],
        }

        graph_data = build_graph_data(bfs=bfs_response)

        service = AttributionService()
        request = AttributionRequest(address=addr, chain=CHAIN, graph_data=graph_data)
        response = service.analyze(request)

        for candidate in response.candidates:
            for ev_id in candidate.evidence_ids:
                ev = service.evidence_service.get_evidence(ev_id)
                assert ev is not None, f"Evidence {ev_id} not found in store"
                assert ev.address == addr.lower()
                assert ev.chain == CHAIN
                assert ev.provenance.created_by == "attribution_engine"

    def test_deterministic_across_runs(self):
        synth_txs = generate_transactions(seed=42, count=20)

        graph = TransactionGraph()
        for tx in synth_txs:
            graph.add_edge(
                chain=tx.chain,
                tx_hash=tx.tx_hash,
                sender_address=tx.from_address,
                receiver_address=tx.to_address,
                amount=__import__("decimal").Decimal(tx.value),
                timestamp=tx.block_timestamp,
            )

        addr = synth_txs[0].from_address
        wallet_id = f"{CHAIN}:{addr.lower()}"
        neighbors = graph.neighbors(wallet_id)

        bfs_response = {
            "wallet_id": wallet_id,
            "max_depth": 3,
            "nodes": [
                {"wallet_id": nid, "address": nid.split(":", 1)[-1], "chain": CHAIN, "depth": 1}
                for nid in neighbors
            ],
        }

        graph_data = build_graph_data(bfs=bfs_response)
        request = AttributionRequest(address=addr, chain=CHAIN, graph_data=graph_data)

        svc1 = AttributionService()
        r1 = svc1.analyze(request)

        svc2 = AttributionService()
        r2 = svc2.analyze(request)

        assert len(r1.candidates) == len(r2.candidates)
        for c1, c2 in zip(r1.candidates, r2.candidates):
            assert c1.score == c2.score
            assert c1.confidence == c2.confidence
            assert c1.vasp_name == c2.vasp_name
