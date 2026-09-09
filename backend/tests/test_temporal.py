from decimal import Decimal

from graph.builder import TransactionEdge, TransactionGraph
from graph import temporal
from graph.synthetic import generate_transactions


def make_edge(tx_hash, sender, receiver, amount=1, timestamp=1000, chain="eth"):
    return TransactionEdge(
        tx_hash=tx_hash,
        chain=chain,
        sender=sender,
        receiver=receiver,
        amount=Decimal(str(amount)),
        timestamp=timestamp,
    )


def build_temporal_graph(edges_data):
    graph = TransactionGraph()
    for i, (sender, receiver, amount, timestamp) in enumerate(edges_data):
        graph.add_edge(
            "eth", f"0x{i:064x}", sender, receiver,
            Decimal(str(amount)), timestamp,
        )
    return graph


class FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def order_by(self, *args):
        return self

    def yield_per(self, batch):
        return iter(self._rows)


class FakeDbSession:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def query(self, model):
        return FakeQuery(self.rows)


def to_row(sender, receiver, index, timestamp):
    from types import SimpleNamespace
    from datetime import datetime, timezone

    return SimpleNamespace(
        chain="eth",
        tx_hash=f"0x{index:064x}",
        block_number=index,
        block_timestamp=datetime.fromtimestamp(timestamp, tz=timezone.utc),
        value=Decimal("1000000000000000000"),
        from_address=sender,
        to_address=receiver,
        id=index,
    )


def test_sort_edges_by_time_ascending():
    edges = [
        make_edge("0x03", "0xa", "0xb", timestamp=300),
        make_edge("0x01", "0xa", "0xb", timestamp=100),
        make_edge("0x02", "0xa", "0xb", timestamp=200),
    ]
    result = temporal.sort_edges_by_time(edges)
    assert [e.timestamp for e in result] == [100, 200, 300]


def test_sort_edges_by_time_descending():
    edges = [
        make_edge("0x01", "0xa", "0xb", timestamp=100),
        make_edge("0x03", "0xa", "0xb", timestamp=300),
        make_edge("0x02", "0xa", "0xb", timestamp=200),
    ]
    result = temporal.sort_edges_by_time(edges, descending=True)
    assert [e.timestamp for e in result] == [300, 200, 100]


def test_sort_edges_stable_for_identical_timestamps():
    e1 = make_edge("0x01", "0xa", "0xb", timestamp=100)
    e2 = make_edge("0x02", "0xa", "0xb", timestamp=100)
    e3 = make_edge("0x03", "0xa", "0xb", timestamp=100)
    result = temporal.sort_edges_by_time([e1, e2, e3])
    assert [e.tx_hash for e in result] == ["0x01", "0x02", "0x03"]


def test_sort_edges_treats_zero_as_earliest():
    edges = [
        make_edge("0x01", "0xa", "0xb", timestamp=500),
        make_edge("0x02", "0xa", "0xb", timestamp=0),
        make_edge("0x03", "0xa", "0xb", timestamp=200),
    ]
    result = temporal.sort_edges_by_time(edges)
    assert [e.timestamp for e in result] == [0, 200, 500]


def test_validate_sequence_valid_chronological():
    edges = [
        make_edge("0x01", "0xa", "0xb", timestamp=100),
        make_edge("0x02", "0xb", "0xc", timestamp=200),
        make_edge("0x03", "0xc", "0xd", timestamp=300),
    ]
    result = temporal.validate_temporal_sequence(edges)
    assert result["is_valid"] is True
    assert result["temporal_valid"] is True
    assert result["chain_valid"] is True
    assert result["violations"] == []


def test_validate_sequence_invalid_temporal_order():
    edges = [
        make_edge("0x01", "0xa", "0xb", timestamp=300),
        make_edge("0x02", "0xb", "0xc", timestamp=100),
    ]
    result = temporal.validate_temporal_sequence(edges)
    assert result["is_valid"] is False
    assert result["temporal_valid"] is False
    assert len(result["violations"]) == 1
    assert result["violations"][0]["type"] == "temporal_order"


def test_validate_sequence_invalid_chain_break():
    edges = [
        make_edge("0x01", "0xa", "0xb", timestamp=100),
        make_edge("0x02", "0xc", "0xd", timestamp=200),
    ]
    result = temporal.validate_temporal_sequence(edges)
    assert result["is_valid"] is False
    assert result["chain_valid"] is False
    assert any(v["type"] == "chain_break" for v in result["violations"])


def test_validate_sequence_empty_list():
    result = temporal.validate_temporal_sequence([])
    assert result["is_valid"] is True
    assert result["violations"] == []


def test_temporal_path_valid_order():
    graph = build_temporal_graph([
        ("0xs", "0a", 1, 100),
        ("0a", "0xt", 1, 200),
    ])
    result = temporal.temporal_path(graph, "eth:0xs", "eth:0xt")
    assert result["found"] is True
    assert result["is_temporally_valid"] is True
    assert result["path"] == ["eth:0xs", "eth:0a", "eth:0xt"]
    assert result["total_hops"] == 2
    assert len(result["edges"]) == 2


def test_temporal_path_invalid_order():
    graph = build_temporal_graph([
        ("0xs", "0a", 1, 200),
        ("0a", "0xt", 1, 100),
    ])
    result = temporal.temporal_path(graph, "eth:0xs", "eth:0xt")
    assert result["found"] is True
    assert result["is_temporally_valid"] is False
    assert len(result["edges"]) == 2


def test_temporal_path_not_found():
    graph = build_temporal_graph([
        ("0xs", "0a", 1, 100),
        ("0b", "0xc", 1, 200),
    ])
    result = temporal.temporal_path(graph, "eth:0xs", "eth:0xc")
    assert result["found"] is False
    assert result["path"] == []
    assert result["edges"] == []
    assert result["is_temporally_valid"] is True
    assert result["total_hops"] is None


def test_temporal_path_source_equals_destination():
    graph = build_temporal_graph([("0xs", "0a", 1, 100)])
    result = temporal.temporal_path(graph, "eth:0xs", "eth:0xs")
    assert result["found"] is True
    assert result["path"] == ["eth:0xs"]
    assert result["edges"] == []
    assert result["is_temporally_valid"] is True
    assert result["total_hops"] == 0


def test_temporal_path_identical_timestamps():
    graph = build_temporal_graph([
        ("0xs", "0a", 1, 100),
        ("0a", "0xt", 1, 100),
    ])
    result = temporal.temporal_path(graph, "eth:0xs", "eth:0xt")
    assert result["found"] is True
    assert result["is_temporally_valid"] is True


def test_temporal_path_returns_edge_details():
    graph = build_temporal_graph([("0xs", "0xt", 50, 100)])
    result = temporal.temporal_path(graph, "eth:0xs", "eth:0xt")
    edge = result["edges"][0]
    assert edge["sender"] == "eth:0xs"
    assert edge["receiver"] == "eth:0xt"
    assert edge["amount"] == "50"
    assert edge["timestamp"] == 100
    assert edge["chain"] == "eth"


def test_temporal_path_with_synthetic_data():
    synthetic = generate_transactions(seed=42, count=10)
    graph = TransactionGraph.from_transactions(
        [
            type("Row", (), {
                "chain": tx.chain,
                "tx_hash": tx.tx_hash,
                "from_address": tx.from_address,
                "to_address": tx.to_address,
                "value": Decimal(tx.value),
                "block_timestamp": type(
                    "TS", (), {"timestamp": lambda self: tx.block_timestamp}
                )(),
            })()
            for tx in synthetic
        ]
    )
    nodes = sorted(
        {n["wallet_id"] for n in graph.nodes},
    )
    source = nodes[0]
    for target in nodes[1:]:
        if graph.bfs_path(source, target)["found"]:
            result = temporal.temporal_path(graph, source, target)
            assert result["found"] is True
            assert result["total_hops"] is not None
            break


def test_temporal_path_service(fake_driver):
    from graph import service
    rows = [
        to_row("0xs", "0a", 1, 100),
        to_row("0a", "0xt", 2, 200),
    ]
    result = service.temporal_path_analysis(
        fake_driver,
        "eth:0xs",
        "eth:0xt",
        db_session_factory=lambda: FakeDbSession(rows),
    )
    assert result["found"] is True
    assert result["is_temporally_valid"] is True
    assert result["total_hops"] == 2


def test_fund_flow_direct_neighbor():
    graph = build_temporal_graph([
        ("0xs", "0xt", 100, 100),
    ])
    result = temporal.fund_flow(graph, "eth:0xs", "eth:0xt")
    assert result["found"] is True
    assert result["wallet_path"] == ["eth:0xs", "eth:0xt"]
    assert result["hop_count"] == 1
    assert len(result["transactions"]) == 1
    assert result["transactions"][0]["sender"] == "eth:0xs"
    assert result["transactions"][0]["receiver"] == "eth:0xt"


def test_fund_flow_multi_hop():
    graph = build_temporal_graph([
        ("0xs", "0a", 100, 100),
        ("0a", "0xt", 200, 200),
    ])
    result = temporal.fund_flow(graph, "eth:0xs", "eth:0xt")
    assert result["found"] is True
    assert result["wallet_path"] == ["eth:0xs", "eth:0a", "eth:0xt"]
    assert result["hop_count"] == 2
    assert len(result["transactions"]) == 2


def test_fund_flow_multiple_transactions_between_pair():
    graph = build_temporal_graph([
        ("0xs", "0a", 100, 100),
        ("0xs", "0a", 100, 300),
        ("0a", "0xt", 200, 200),
    ])
    result = temporal.fund_flow(graph, "eth:0xs", "eth:0xt")
    assert result["found"] is True
    assert len(result["transactions"]) == 3
    assert [t["timestamp"] for t in result["transactions"]] == [100, 200, 300]


def test_fund_flow_source_equals_destination():
    graph = build_temporal_graph([("0xs", "0a", 100, 100)])
    result = temporal.fund_flow(graph, "eth:0xs", "eth:0xs")
    assert result["found"] is True
    assert result["wallet_path"] == ["eth:0xs"]
    assert result["hop_count"] == 0
    assert result["transactions"] == []


def test_fund_flow_not_found():
    graph = build_temporal_graph([
        ("0xs", "0a", 100, 100),
        ("0b", "0c", 200, 200),
    ])
    result = temporal.fund_flow(graph, "eth:0xs", "eth:0c")
    assert result["found"] is False
    assert result["wallet_path"] == []
    assert result["transactions"] == []
    assert result["hop_count"] is None


def test_fund_flow_preserves_chronological_order():
    graph = build_temporal_graph([
        ("0xs", "0a", 100, 300),
        ("0a", "0xt", 200, 100),
    ])
    result = temporal.fund_flow(graph, "eth:0xs", "eth:0xt")
    assert result["found"] is True
    assert [t["timestamp"] for t in result["transactions"]] == [100, 300]


def test_fund_flow_handles_cycles():
    graph = build_temporal_graph([
        ("0xs", "0a", 10, 100),
        ("0a", "0b", 10, 200),
        ("0b", "0a", 10, 300),
        ("0a", "0a", 10, 400),
        ("0b", "0xt", 10, 500),
    ])
    result = temporal.fund_flow(graph, "eth:0xs", "eth:0xt")
    assert result["found"] is True
    assert result["wallet_path"][-1] == "eth:0xt"
    assert result["transactions"][-1]["receiver"] == "eth:0xt"


def test_fund_flow_returns_all_required_fields():
    graph = build_temporal_graph([
        ("0xs", "0xt", 50, 100),
    ])
    result = temporal.fund_flow(graph, "eth:0xs", "eth:0xt")
    tx = result["transactions"][0]
    assert result["source"] == "eth:0xs"
    assert result["destination"] == "eth:0xt"
    for key in ("tx_hash", "chain", "sender", "receiver", "amount", "timestamp"):
        assert key in tx


def test_fund_flow_with_synthetic_data():
    synthetic = generate_transactions(seed=7, count=10)
    graph = TransactionGraph.from_transactions(
        [
            type("Row", (), {
                "chain": tx.chain,
                "tx_hash": tx.tx_hash,
                "from_address": tx.from_address,
                "to_address": tx.to_address,
                "value": Decimal(tx.value),
                "block_timestamp": type(
                    "TS", (), {"timestamp": lambda self: tx.block_timestamp}
                )(),
            })()
            for tx in synthetic
        ]
    )
    nodes = sorted({n["wallet_id"] for n in graph.nodes})
    source = nodes[0]
    for target in nodes[1:]:
        if graph.bfs_path(source, target)["found"]:
            result = temporal.fund_flow(graph, source, target)
            assert result["found"] is True
            assert len(result["wallet_path"]) > 1
            timestamps = [t["timestamp"] for t in result["transactions"]]
            assert timestamps == sorted(timestamps)
            break


def test_fund_flow_service(fake_driver):
    from graph import service
    rows = [
        to_row("0xs", "0a", 1, 100),
        to_row("0a", "0xt", 2, 200),
    ]
    result = service.fund_flow_analysis(
        fake_driver,
        "eth:0xs",
        "eth:0xt",
        db_session_factory=lambda: FakeDbSession(rows),
    )
    assert result["found"] is True
    assert result["hop_count"] == 2
    assert len(result["transactions"]) == 2
