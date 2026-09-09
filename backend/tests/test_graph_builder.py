from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from graph.builder import TransactionGraph
from graph.synthetic import generate_transactions


def to_row(synthetic):
    return SimpleNamespace(
        chain=synthetic.chain,
        tx_hash=synthetic.tx_hash,
        from_address=synthetic.from_address,
        to_address=synthetic.to_address,
        value=Decimal(synthetic.value),
        block_timestamp=datetime.fromtimestamp(
            synthetic.block_timestamp, tz=timezone.utc
        ),
    )


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


def test_unique_wallets_become_nodes():
    graph = TransactionGraph()
    graph.add_row(to_row(generate_transactions(seed=1, count=10)[0]))
    assert graph.node_count == 2
    assert all(node["wallet_id"].startswith("eth:") for node in graph.nodes)


def test_each_transaction_is_single_directed_edge():
    synthetic = generate_transactions(seed=7, count=20)
    graph = TransactionGraph.from_transactions([to_row(tx) for tx in synthetic])
    assert graph.edge_count == len(synthetic)
    assert graph.node_count > 2
    for edge in graph.edges:
        assert edge.sender != edge.receiver
        assert graph.has_node(edge.sender)
        assert graph.has_node(edge.receiver)


def test_required_fields_preserved_on_edge():
    synthetic = generate_transactions(seed=3, count=1)[0]
    graph = TransactionGraph()
    graph.add_row(to_row(synthetic))
    edge = graph.edges[0]
    assert edge.tx_hash == synthetic.tx_hash
    assert edge.chain == synthetic.chain
    assert edge.sender.endswith(synthetic.from_address.lower())
    assert edge.receiver.endswith(synthetic.to_address.lower())
    assert edge.amount == Decimal(synthetic.value)
    assert edge.timestamp == synthetic.block_timestamp


def test_duplicate_chain_tx_hash_not_duplicated():
    row = to_row(generate_transactions(seed=4, count=1)[0])
    graph = TransactionGraph()
    graph.add_row(row)
    graph.add_row(row)
    assert graph.edge_count == 1
    assert graph.node_count == 2


def test_multi_chain_nodes_stay_isolated():
    graph = TransactionGraph()
    address = "0x" + "a" * 40
    graph.add_edge("eth", "0x" + "1" * 64, address, "0x" + "b" * 40, Decimal(1), 1)
    graph.add_edge("bsc", "0x" + "2" * 64, address, "0x" + "c" * 40, Decimal(2), 2)
    assert graph.node_count == 4
    assert graph.has_node(f"eth:{address.lower()}")
    assert graph.has_node(f"bsc:{address.lower()}")


def test_out_and_in_edge_accessors():
    graph = TransactionGraph.from_transactions(
        [to_row(tx) for tx in generate_transactions(seed=5, count=5)]
    )
    pivot = graph.edges[0]
    assert any(edge.tx_hash == pivot.tx_hash for edge in graph.get_edges_from(pivot.sender))
    assert any(edge.tx_hash == pivot.tx_hash for edge in graph.get_edges_to(pivot.receiver))
    assert graph.get_edges_from("eth:nonexistent") == []
    assert graph.get_edges_to("eth:nonexistent") == []


def test_build_reads_from_database():
    synthetic = generate_transactions(seed=9, count=15)
    rows = [to_row(tx) for tx in synthetic]
    graph = TransactionGraph.build(db_session_factory=lambda: FakeDbSession(rows))
    expected_wallets = {
        f"{tx.chain}:{address.lower()}"
        for tx in synthetic
        for address in (tx.from_address, tx.to_address)
    }
    assert graph.node_count == len(expected_wallets)
    assert graph.edge_count == 15


def test_build_empty_database_produces_empty_graph():
    graph = TransactionGraph.build(db_session_factory=lambda: FakeDbSession([]))
    assert graph.node_count == 0
    assert graph.edge_count == 0


def test_add_row_skips_missing_fields():
    base = to_row(generate_transactions(seed=12, count=1)[0])
    graph = TransactionGraph()
    graph.add_row(SimpleNamespace(
        chain=base.chain, block_timestamp=base.block_timestamp,
        from_address=base.from_address, to_address=base.to_address,
        value=base.value,
    ))
    graph.add_row(SimpleNamespace(
        chain=base.chain, tx_hash=base.tx_hash, block_timestamp=base.block_timestamp,
        from_address=base.from_address, to_address=base.to_address,
    ))
    graph.add_row(SimpleNamespace(
        chain=base.chain, tx_hash=base.tx_hash, block_timestamp=base.block_timestamp,
        from_address=base.from_address, value=base.value,
    ))
    assert graph.node_count == 0
    assert graph.edge_count == 0


def test_add_row_skips_invalid_value():
    base = to_row(generate_transactions(seed=13, count=1)[0])
    graph = TransactionGraph()
    graph.add_row(SimpleNamespace(
        chain=base.chain, tx_hash=base.tx_hash, block_timestamp=base.block_timestamp,
        from_address=base.from_address, to_address=base.to_address, value=None,
    ))
    graph.add_row(SimpleNamespace(
        chain=base.chain, tx_hash=base.tx_hash, block_timestamp=base.block_timestamp,
        from_address=base.from_address, to_address=base.to_address, value="not-a-number",
    ))
    assert graph.node_count == 0
    assert graph.edge_count == 0


def test_add_row_accepts_dict_rows():
    graph = TransactionGraph()
    graph.add_row({
        "chain": "eth",
        "tx_hash": "0x" + "b" * 64,
        "block_timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "from_address": "0x" + "1" * 40,
        "to_address": "0x" + "2" * 40,
        "value": "1000000000000000000",
    })
    assert graph.edge_count == 1
    edge = graph.edges[0]
    assert edge.sender == "eth:0x" + "1" * 40
    assert edge.receiver == "eth:0x" + "2" * 40
    assert edge.amount == Decimal("1000000000000000000")
    assert edge.timestamp == 1704067200


def test_add_row_missing_block_timestamp_defaults_zero():
    graph = TransactionGraph()
    graph.add_row({
        "chain": "eth",
        "tx_hash": "0x" + "c" * 64,
        "from_address": "0x" + "3" * 40,
        "to_address": "0x" + "4" * 40,
        "value": Decimal("1"),
    })
    assert graph.edge_count == 1
    assert graph.edges[0].timestamp == 0


def test_build_deduplicates_duplicate_rows():
    row = SimpleNamespace(
        chain="eth",
        tx_hash="0x" + "d" * 64,
        block_timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        from_address="0x" + "5" * 40,
        to_address="0x" + "6" * 40,
        value=Decimal("10"),
    )
    graph = TransactionGraph.build(
        db_session_factory=lambda: FakeDbSession([row, row])
    )
    assert graph.edge_count == 1
    assert graph.node_count == 2


def test_to_dict_serializes_graph():
    graph = TransactionGraph.from_transactions(
        [to_row(tx) for tx in generate_transactions(seed=11, count=3)]
    )
    payload = graph.to_dict()
    assert payload["node_count"] == graph.node_count
    assert payload["edge_count"] == 3
    assert payload["edges"][0]["amount"].isdigit()
    assert isinstance(payload["edges"][0]["timestamp"], int)


def build_graph(edges):
    graph = TransactionGraph()
    for index, (chain, sender, receiver) in enumerate(edges):
        graph.add_edge(
            chain,
            f"0x{index:064x}",
            sender,
            receiver,
            Decimal("1"),
            index,
        )
    return graph


def test_bfs_path_direct_neighbor():
    graph = build_graph([("eth", "0xs", "0xa")])
    result = graph.bfs_path("eth:0xs", "eth:0xa")
    assert result["found"] is True
    assert result["hop_count"] == 1
    assert result["path"] == ["eth:0xs", "eth:0xa"]


def test_bfs_path_multi_hop():
    graph = build_graph(
        [
            ("eth", "0xs", "0xa"),
            ("eth", "0xa", "0xb"),
            ("eth", "0xb", "0xt"),
        ]
    )
    result = graph.bfs_path("eth:0xs", "eth:0xt")
    assert result["found"] is True
    assert result["hop_count"] == 3
    assert result["path"] == ["eth:0xs", "eth:0xa", "eth:0xb", "eth:0xt"]


def test_bfs_path_source_equals_destination():
    graph = build_graph([("eth", "0xs", "0xa")])
    result = graph.bfs_path("eth:0xs", "eth:0xs")
    assert result["found"] is True
    assert result["hop_count"] == 0
    assert result["path"] == ["eth:0xs"]


def test_bfs_path_nonexistent_source():
    graph = build_graph([("eth", "0xs", "0xa")])
    result = graph.bfs_path("eth:0ghost", "eth:0xa")
    assert result["found"] is False
    assert result["hop_count"] is None
    assert result["path"] == []


def test_bfs_path_nonexistent_destination():
    graph = build_graph([("eth", "0xs", "0xa")])
    result = graph.bfs_path("eth:0xs", "eth:0ghost")
    assert result["found"] is False
    assert result["hop_count"] is None
    assert result["path"] == []


def test_bfs_path_disconnected_wallets():
    graph = build_graph(
        [
            ("eth", "0xs", "0xa"),
            ("eth", "0b", "0c"),
        ]
    )
    result = graph.bfs_path("eth:0xs", "eth:0c")
    assert result["found"] is False
    assert result["hop_count"] is None
    assert result["path"] == []


def test_bfs_path_handles_cycles():
    graph = build_graph(
        [
            ("eth", "0xs", "0xa"),
            ("eth", "0xa", "0xb"),
            ("eth", "0xb", "0xa"),
            ("eth", "0xa", "0xa"),
            ("eth", "0xb", "0xt"),
        ]
    )
    result = graph.bfs_path("eth:0xs", "eth:0xt")
    assert result["found"] is True
    assert result["hop_count"] == 3
    assert result["path"] == ["eth:0xs", "eth:0xa", "eth:0xb", "eth:0xt"]


def test_bfs_path_returns_shortest_of_multiple_paths():
    graph = build_graph(
        [
            ("eth", "0xs", "0a"),
            ("eth", "0a", "0xt"),
            ("eth", "0xs", "0p"),
            ("eth", "0p", "0q"),
            ("eth", "0q", "0r"),
            ("eth", "0r", "0xt"),
        ]
    )
    result = graph.bfs_path("eth:0xs", "eth:0xt")
    assert result["found"] is True
    assert result["hop_count"] == 2
    assert result["path"] == ["eth:0xs", "eth:0a", "eth:0xt"]


def test_bfs_path_traverses_undirected_edges():
    graph = build_graph(
        [
            ("eth", "0a", "0xs"),
            ("eth", "0b", "0a"),
            ("eth", "0xt", "0b"),
        ]
    )
    result = graph.bfs_path("eth:0xs", "eth:0xt")
    assert result["found"] is True
    assert result["hop_count"] == 3
    assert result["path"] == ["eth:0xs", "eth:0a", "eth:0b", "eth:0xt"]


def test_dfs_path_direct_neighbor():
    graph = build_graph([("eth", "0xs", "0xt")])
    result = graph.dfs_path("eth:0xs", "eth:0xt")
    assert result["found"] is True
    assert result["hop_count"] == 1
    assert result["path"] == ["eth:0xs", "eth:0xt"]


def test_dfs_path_multi_hop():
    graph = build_graph(
        [
            ("eth", "0xs", "0xa"),
            ("eth", "0xa", "0xb"),
            ("eth", "0xb", "0xt"),
        ]
    )
    result = graph.dfs_path("eth:0xs", "eth:0xt")
    assert result["found"] is True
    assert result["hop_count"] == 3
    assert result["path"] == ["eth:0xs", "eth:0xa", "eth:0xb", "eth:0xt"]


def test_dfs_path_source_equals_destination():
    graph = build_graph([("eth", "0xs", "0xa")])
    result = graph.dfs_path("eth:0xs", "eth:0xs")
    assert result["found"] is True
    assert result["hop_count"] == 0
    assert result["path"] == ["eth:0xs"]


def test_dfs_path_nonexistent_source():
    graph = build_graph([("eth", "0xs", "0xa")])
    result = graph.dfs_path("eth:0ghost", "eth:0xa")
    assert result["found"] is False
    assert result["hop_count"] is None
    assert result["path"] == []


def test_dfs_path_nonexistent_destination():
    graph = build_graph([("eth", "0xs", "0xa")])
    result = graph.dfs_path("eth:0xs", "eth:0ghost")
    assert result["found"] is False
    assert result["hop_count"] is None
    assert result["path"] == []


def test_dfs_path_disconnected_wallets():
    graph = build_graph(
        [
            ("eth", "0xs", "0xa"),
            ("eth", "0b", "0c"),
        ]
    )
    result = graph.dfs_path("eth:0xs", "eth:0c")
    assert result["found"] is False
    assert result["hop_count"] is None
    assert result["path"] == []


def test_dfs_path_handles_cycles():
    graph = build_graph(
        [
            ("eth", "0xs", "0xa"),
            ("eth", "0xa", "0xb"),
            ("eth", "0xb", "0xa"),
            ("eth", "0xa", "0xa"),
            ("eth", "0xb", "0xt"),
        ]
    )
    result = graph.dfs_path("eth:0xs", "eth:0xt")
    assert result["found"] is True
    assert result["hop_count"] == 3
    assert result["path"] == ["eth:0xs", "eth:0xa", "eth:0xb", "eth:0xt"]


def test_dfs_path_returns_valid_path_for_multiple_options():
    graph = build_graph(
        [
            ("eth", "0xs", "0a"),
            ("eth", "0a", "0b"),
            ("eth", "0b", "0c"),
            ("eth", "0c", "0xt"),
            ("eth", "0xs", "0z"),
            ("eth", "0z", "0xt"),
        ]
    )
    result = graph.dfs_path("eth:0xs", "eth:0xt")
    assert result["found"] is True
    assert result["path"][0] == "eth:0xs"
    assert result["path"][-1] == "eth:0xt"
    assert result["hop_count"] == len(result["path"]) - 1


def test_dfs_path_does_not_guarantee_shortest_path():
    graph = build_graph(
        [
            ("eth", "0xs", "0a"),
            ("eth", "0a", "0b"),
            ("eth", "0b", "0c"),
            ("eth", "0c", "0xt"),
            ("eth", "0xs", "0z"),
            ("eth", "0z", "0xt"),
        ]
    )
    result = graph.dfs_path("eth:0xs", "eth:0xt")
    assert result["hop_count"] == 4
    assert result["path"] == ["eth:0xs", "eth:0a", "eth:0b", "eth:0c", "eth:0xt"]


def test_dfs_path_traverses_undirected_edges():
    graph = build_graph(
        [
            ("eth", "0a", "0xs"),
            ("eth", "0b", "0a"),
            ("eth", "0xt", "0b"),
        ]
    )
    result = graph.dfs_path("eth:0xs", "eth:0xt")
    assert result["found"] is True
    assert result["hop_count"] == 3
    assert result["path"] == ["eth:0xs", "eth:0a", "eth:0b", "eth:0xt"]


def test_shortest_path_hop_count_matches_bfs():
    graph = build_graph(
        [
            ("eth", "0xs", "0a"),
            ("eth", "0a", "0xt"),
            ("eth", "0xs", "0p"),
            ("eth", "0p", "0q"),
            ("eth", "0q", "0xt"),
        ]
    )
    bfs = graph.bfs_path("eth:0xs", "eth:0xt")
    sp = graph.shortest_path("eth:0xs", "eth:0xt")
    assert sp["path_exists"] is True
    assert sp["hop_count"] == bfs["hop_count"]
    assert sp["path"] == bfs["path"]


def test_shortest_path_source_equals_destination():
    graph = build_graph([("eth", "0xs", "0xa")])
    result = graph.shortest_path("eth:0xs", "eth:0xs")
    assert result["path_exists"] is True
    assert result["hop_count"] == 0
    assert result["path"] == ["eth:0xs"]


def test_shortest_path_nonexistent_source():
    graph = build_graph([("eth", "0xs", "0xa")])
    result = graph.shortest_path("eth:0ghost", "eth:0xa")
    assert result["path_exists"] is False
    assert result["hop_count"] is None
    assert result["path"] == []


def test_shortest_path_disconnected():
    graph = build_graph(
        [
            ("eth", "0xs", "0a"),
            ("eth", "0b", "0c"),
        ]
    )
    result = graph.shortest_path("eth:0xs", "eth:0c")
    assert result["path_exists"] is False
    assert result["path"] == []


def test_shortest_path_returns_shortest_of_multiple():
    graph = build_graph(
        [
            ("eth", "0xs", "0a"),
            ("eth", "0a", "0xt"),
            ("eth", "0xs", "0p"),
            ("eth", "0p", "0q"),
            ("eth", "0q", "0xt"),
        ]
    )
    result = graph.shortest_path("eth:0xs", "eth:0xt")
    assert result["path_exists"] is True
    assert result["hop_count"] == 2
    assert result["path"] == ["eth:0xs", "eth:0a", "eth:0xt"]


def build_weighted_graph(edges_with_weights):
    graph = TransactionGraph()
    for i, (sender, receiver, amount, ts) in enumerate(edges_with_weights):
        graph.add_edge(
            "eth", f"0x{i:064x}", sender, receiver,
            Decimal(str(amount)), ts,
        )
    return graph


def test_weighted_path_hops_matches_bfs():
    graph = build_weighted_graph([
        ("0xs", "0a", 100, 1),
        ("0a", "0xt", 200, 2),
    ])
    from graph.builder import hop_weight

    result = graph.weighted_path("eth:0xs", "eth:0xt", weight_fn=hop_weight)
    bfs = graph.bfs_path("eth:0xs", "eth:0xt")
    assert result["path_exists"] is True
    assert result["hop_count"] == bfs["hop_count"]
    assert result["path"] == bfs["path"]
    assert result["total_cost"] == 2.0


def test_weighted_path_amount_prefers_low_cost():
    graph = build_weighted_graph([
        ("0xs", "0a", 100, 1),
        ("0a", "0xt", 100, 2),
        ("0xs", "0z", 1000, 3),
        ("0z", "0xt", 1000, 4),
    ])
    from graph.builder import amount_weight

    result = graph.weighted_path("eth:0xs", "eth:0xt", weight_fn=amount_weight)
    assert result["path_exists"] is True
    assert result["path"] == ["eth:0xs", "eth:0a", "eth:0xt"]
    assert result["total_cost"] == 200.0
    assert result["hop_count"] == 2


def test_weighted_path_source_equals_destination():
    graph = build_weighted_graph([("0xs", "0a", 100, 1)])
    result = graph.weighted_path("eth:0xs", "eth:0xs")
    assert result["path_exists"] is True
    assert result["total_cost"] == 0.0
    assert result["hop_count"] == 0
    assert result["path"] == ["eth:0xs"]


def test_weighted_path_nonexistent_source():
    graph = build_weighted_graph([("0xs", "0a", 100, 1)])
    result = graph.weighted_path("eth:0ghost", "eth:0a")
    assert result["path_exists"] is False
    assert result["total_cost"] is None
    assert result["path"] == []


def test_weighted_path_disconnected():
    graph = build_weighted_graph([
        ("0xs", "0a", 100, 1),
        ("0b", "0c", 200, 2),
    ])
    result = graph.weighted_path("eth:0xs", "eth:0c")
    assert result["path_exists"] is False
    assert result["total_cost"] is None


def test_weighted_path_handles_cycles():
    graph = build_weighted_graph([
        ("0xs", "0a", 10, 1),
        ("0a", "0b", 10, 2),
        ("0b", "0a", 10, 3),
        ("0a", "0a", 10, 4),
        ("0b", "0xt", 10, 5),
    ])
    from graph.builder import amount_weight

    result = graph.weighted_path("eth:0xs", "eth:0xt", weight_fn=amount_weight)
    assert result["path_exists"] is True
    assert result["total_cost"] == 30.0
    assert result["hop_count"] == 3


def test_weighted_path_total_cost_is_sum_of_weights():
    graph = build_weighted_graph([
        ("0xs", "0a", 50, 1),
        ("0a", "0xt", 75, 2),
    ])
    from graph.builder import amount_weight

    result = graph.weighted_path("eth:0xs", "eth:0xt", weight_fn=amount_weight)
    assert result["total_cost"] == 125.0
    assert result["hop_count"] == 2


def test_weighted_path_custom_weight_fn():
    graph = build_weighted_graph([
        ("0xs", "0a", 100, 1000),
        ("0a", "0xt", 100, 2000),
    ])
    result = graph.weighted_path(
        "eth:0xs", "eth:0xt", weight_fn=lambda e: float(e.timestamp)
    )
    assert result["path_exists"] is True
    assert result["total_cost"] == 3000.0