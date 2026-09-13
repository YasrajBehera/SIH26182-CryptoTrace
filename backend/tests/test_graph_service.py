from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from graph import service


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


class FakeTransactionRow:
    chain = "eth"
    tx_hash = "0xabcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
    block_number = 1
    block_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
    value = Decimal("1000000000000000000")
    from_address = "0x1111111111111111111111111111111111111111"
    to_address = "0x2222222222222222222222222222222222222222"
    id = 7


def test_sync_from_postgres(monkeypatch, fake_driver):
    monkeypatch.setattr(service, "ensure_database_tables", lambda: None)
    rows = [FakeTransactionRow(), FakeTransactionRow()]
    result = service.sync_from_postgres(
        fake_driver, db_session_factory=lambda: FakeDbSession(rows)
    )
    assert result == {"synced": 2}

    merges = [
        (query, params)
        for (query, params) in fake_driver._session.queries
        if "MERGE (tx:Transaction" in query
    ]
    assert len(merges) == 2
    params = merges[0][1]
    assert params["tx_id"] == "eth:0xabcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
    assert params["src_wid"] == "eth:0x1111111111111111111111111111111111111111"
    assert params["dst_wid"] == "eth:0x2222222222222222222222222222222222222222"
    assert params["block_timestamp"] == 1704067200
    assert params["value"] == "1000000000000000000"


def test_merge_transactions_writes_durable_rows(fake_driver):
    rows = [
        {
            "chain": "ETH",
            "tx_hash": "0xABC",
            "block_number": 10,
            "block_timestamp": 1704067200,
            "from_address": "0x1111111111111111111111111111111111111111",
            "to_address": "0x2222222222222222222222222222222222222222",
            "value": "500000000000000000",
        }
    ]
    synced = service.merge_transactions(fake_driver, rows)
    assert synced == 1

    merges = [
        (query, params)
        for (query, params) in fake_driver._session.queries
        if "MERGE (tx:Transaction" in query
    ]
    assert len(merges) == 1
    params = merges[0][1]
    assert params["tx_id"] == "eth:0xabc"
    assert params["src_wid"] == "eth:0x1111111111111111111111111111111111111111"
    assert params["dst_wid"] == "eth:0x2222222222222222222222222222222222222222"
    assert params["block_timestamp"] == 1704067200


def test_bfs_returns_neighbors_by_depth(fake_session, fake_driver):
    fake_session.bfs_records = [
        {"wallet_id": "eth:0xbb", "address": "0xbb", "chain": "eth", "depth": 1},
        {"wallet_id": "eth:0xcc", "address": "0xcc", "chain": "eth", "depth": 2},
    ]
    rows = service.bfs(fake_driver, "eth:0xaa", max_depth=3)
    assert [row["depth"] for row in rows] == [1, 2]
    assert rows[1]["wallet_id"] == "eth:0xcc"


def test_bfs_depth_injected_as_validated_literal_not_parameter(fake_session, fake_driver):
    service.bfs(fake_driver, "eth:0xaa", max_depth=3)
    query, params = fake_session.queries[-1]
    assert "[*1..3]" in query
    assert "$max_depth" not in query
    assert "max_depth" not in params
    assert params["max_nodes"] == 100
    assert params["wallet_id"] == "eth:0xaa"


def test_bfs_max_depth_validation(fake_session, fake_driver):
    for bad in (0, -1, 51, "abc", None, "3; MATCH (x) DETACH DELETE x"):
        with pytest.raises((ValueError, TypeError)):
            service.bfs(fake_driver, "eth:0xaa", max_depth=bad)


def test_bfs_max_depth_boundary_allowed(fake_session, fake_driver):
    service.bfs(fake_driver, "eth:0xaa", max_depth=service.MAX_BFS_DEPTH)
    query, _ = fake_session.queries[-1]
    assert f"[*1..{service.MAX_BFS_DEPTH}]" in query


def test_bfs_runs_on_live_neo4j_no_syntax_error():
    try:
        from graph.neo4j_client import create_driver, is_neo4j_healthy

        driver = create_driver()
    except Exception:
        pytest.skip("neo4j client/driver unavailable")
    try:
        if not is_neo4j_healthy(driver):
            pytest.skip("live Neo4j container not reachable")
        rows = service.bfs(
            driver,
            "eth:0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
            max_depth=3,
        )
        assert isinstance(rows, list)
        assert all(set(row) >= {"wallet_id", "address", "chain", "depth"} for row in rows)
    finally:
        driver.close()


def test_dfs_returns_distinct_wallets(fake_session, fake_driver):
    fake_session.bfs_records = [
        {"wallet_id": "eth:0xcc", "address": "0xcc", "chain": "eth", "depth": 1},
        {"wallet_id": "eth:0xbb", "address": "0xbb", "chain": "eth", "depth": 1},
    ]
    rows = service.dfs(fake_driver, "eth:0xaa", max_depth=4)
    assert rows[0]["wallet_id"] == "eth:0xaa"
    assert rows[0]["address"] == "0xaa"
    assert rows[0]["chain"] == "eth"
    visited = [row["wallet_id"] for row in rows]
    assert "eth:0xaa" in visited
    assert len(rows) == len(set(visited))


def test_dfs_never_requires_apoc():
    assert "apoc.path.expand" not in service.NEIGHBORS_QUERY
    for bad in (0, -1, 51, "abc", None, "3; MATCH (x) DETACH DELETE x"):
        with pytest.raises((ValueError, TypeError)):
            service.dfs(fake_driver_arg_noop(), "eth:0xaa", max_depth=bad)


def fake_driver_arg_noop():
    return None


def test_neighbors_returns_only_direct_counterparts(fake_session, fake_driver):
    fake_session.bfs_records = [
        {"wallet_id": "eth:0xbb", "address": "0xbb", "chain": "eth", "depth": 1},
        {"wallet_id": "eth:0xcc", "address": "0xcc", "chain": "eth", "depth": 1},
    ]
    rows = service.neighbors(fake_driver, "eth:0xaa")
    assert [row["depth"] for row in rows] == [1, 1]
    assert all(row["wallet_id"] in {"eth:0xbb", "eth:0xcc"} for row in rows)


def test_neighbors_query_spans_transaction_in_both_directions():
    query = service.NEIGHBORS_QUERY
    assert "(start)-[:SENT]->(tx:Transaction)-[:RECEIVED]->(other:Wallet)" in query
    assert "(other:Wallet)-[:SENT]->(tx:Transaction)-[:RECEIVED]->(start)" in query


def test_temporal_flow_queries_use_correct_relationship_direction():
    out_query = service.TEMPLATE_OUT_FLOW
    in_query = service.TEMPLATE_IN_FLOW
    assert (
        "(wallet)-[s:SENT]->(tx:Transaction)-[r:RECEIVED]->(counterparty:Wallet)"
        in out_query
    )
    assert (
        "(counterparty:Wallet)-[s:SENT]->(tx:Transaction)-[r:RECEIVED]->(wallet)"
        in in_query
    )
    assert "<-[r:RECEIVED]" not in out_query
    assert "<-[r:RECEIVED]" not in in_query


def test_temporal_flow_direction_out_uses_out_template(fake_session, fake_driver):
    service.temporal_flow(fake_driver, "eth:0xwallet", direction="out")
    query = fake_session.queries[0][0]
    assert "(wallet)-[s:SENT]->(tx:Transaction)-[r:RECEIVED]->(counterparty:Wallet)" in query


def test_clusters_uses_component_column_for_wcc():
    query = service.CLUSTER_QUERY.format(
        procedure=service.CLUSTER_PROCEDURES["wcc"],
        column=service.CLUSTER_COLUMNS["wcc"],
    )
    assert "YIELD nodeId, componentId" in query
    assert "WITH componentId AS community_id" in query


def test_clusters_uses_community_column_for_louvain():
    query = service.CLUSTER_QUERY.format(
        procedure=service.CLUSTER_PROCEDURES["louvain"],
        column=service.CLUSTER_COLUMNS["louvain"],
    )
    assert "YIELD nodeId, communityId" in query


def test_shortest_path_unweighted(fake_session, fake_driver):
    result = service.shortest_path(fake_driver, "eth:0xsrc", "eth:0xdest")
    assert result["found"] is True
    assert result["weight"] == "hops"
    assert result["total_cost"] == 2.0
    assert result["nodes"][0]["label"] == "Wallet"


def test_shortest_path_weighted_by_amount(fake_session, fake_driver):
    result = service.shortest_path(
        fake_driver, "eth:0xsrc", "eth:0xdest", weight="amount"
    )
    assert result["weight"] == "amount"
    _, params = fake_session.queries[-1]
    assert params["weight"] == "amount_value"


def test_shortest_path_missing_target(fake_session, fake_driver):
    fake_session.no_ids = True
    result = service.shortest_path(fake_driver, "eth:0xsrc", "eth:0xgone")
    assert result["found"] is False
    assert result["nodes"] == []


def test_temporal_flow_builds_window(fake_session, fake_driver):
    flows = service.temporal_flow(
        fake_driver, "eth:0xwallet", from_ts=1000, to_ts=2000
    )
    assert len(fake_session.queries) == 2
    assert len(flows) == 2
    combined = " ".join(query for query, _ in fake_session.queries)
    assert "tx.block_timestamp >= $from_ts" in combined
    assert "tx.block_timestamp <= $to_ts" in combined
    assert flows[0]["tx_hash"] == "0xabc"


def test_temporal_flow_direction_out(fake_session, fake_driver):
    service.temporal_flow(fake_driver, "eth:0xwallet", direction="out")
    assert len(fake_session.queries) == 1


def test_clusters_filters_small_communities(fake_session, fake_driver):
    fake_session.cluster_records = [
        {
            "community_id": 7,
            "wallets": [
                {"wallet_id": "a", "address": "a", "chain": "eth"},
                {"wallet_id": "b", "address": "b", "chain": "eth"},
            ],
        },
        {
            "community_id": 8,
            "wallets": [{"wallet_id": "c", "address": "c", "chain": "eth"}],
        },
    ]
    result = service.clusters(fake_driver, algorithm="louvain", min_community_size=2)
    assert [item["community_id"] for item in result] == [7]
    procedures = " ".join(query for query, _ in fake_session.queries)
    assert "gds.louvain.stream" in procedures


def test_clusters_rejects_unknown_algorithm(fake_driver):
    with pytest.raises(ValueError):
        service.clusters(fake_driver, algorithm="k-means")


def transaction_row(index, sender, receiver):
    return SimpleNamespace(
        chain="eth",
        tx_hash=f"0x{index:064x}",
        block_number=index,
        block_timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        value=Decimal("1000000000000000000"),
        from_address=sender,
        to_address=receiver,
        id=index,
    )


def test_bfs_shortest_path_builds_graph_and_finds_path(fake_driver):
    rows = [
        transaction_row(1, "0xs", "0xa"),
        transaction_row(2, "0xa", "0xb"),
        transaction_row(3, "0xb", "0xt"),
    ]
    result = service.bfs_shortest_path(
        fake_driver,
        "eth:0xs",
        "eth:0xt",
        db_session_factory=lambda: FakeDbSession(rows),
    )
    assert result["found"] is True
    assert result["hop_count"] == 3
    assert result["path"] == ["eth:0xs", "eth:0xa", "eth:0xb", "eth:0xt"]


def test_bfs_shortest_path_disconnected(fake_driver):
    rows = [
        transaction_row(1, "0xs", "0xa"),
        transaction_row(2, "0b", "0c"),
    ]
    result = service.bfs_shortest_path(
        fake_driver,
        "eth:0xs",
        "eth:0c",
        db_session_factory=lambda: FakeDbSession(rows),
    )
    assert result["found"] is False
    assert result["hop_count"] is None
    assert result["path"] == []


def test_bfs_shortest_path_nonexistent_wallet(fake_driver):
    rows = [transaction_row(1, "0xs", "0xa")]
    result = service.bfs_shortest_path(
        fake_driver,
        "eth:0ghost",
        "eth:0a",
        db_session_factory=lambda: FakeDbSession(rows),
    )
    assert result["found"] is False
    assert result["path"] == []


def test_dfs_path_builds_graph_and_finds_path(fake_driver):
    rows = [
        transaction_row(1, "0xs", "0xa"),
        transaction_row(2, "0xa", "0xb"),
        transaction_row(3, "0xb", "0xt"),
    ]
    result = service.dfs_path(
        fake_driver,
        "eth:0xs",
        "eth:0xt",
        db_session_factory=lambda: FakeDbSession(rows),
    )
    assert result["found"] is True
    assert result["hop_count"] == 3
    assert result["path"] == ["eth:0xs", "eth:0xa", "eth:0xb", "eth:0xt"]


def test_dfs_path_disconnected(fake_driver):
    rows = [
        transaction_row(1, "0xs", "0xa"),
        transaction_row(2, "0b", "0c"),
    ]
    result = service.dfs_path(
        fake_driver,
        "eth:0xs",
        "eth:0c",
        db_session_factory=lambda: FakeDbSession(rows),
    )
    assert result["found"] is False
    assert result["hop_count"] is None
    assert result["path"] == []


def test_dfs_path_nonexistent_wallet(fake_driver):
    rows = [transaction_row(1, "0xs", "0xa")]
    result = service.dfs_path(
        fake_driver,
        "eth:0ghost",
        "eth:0a",
        db_session_factory=lambda: FakeDbSession(rows),
    )
    assert result["found"] is False
    assert result["path"] == []


def test_shortest_path_by_hops_builds_graph_and_finds_path(fake_driver):
    rows = [
        transaction_row(1, "0xs", "0a"),
        transaction_row(2, "0a", "0xb"),
        transaction_row(3, "0xb", "0xt"),
    ]
    result = service.shortest_path_by_hops(
        fake_driver,
        "eth:0xs",
        "eth:0xt",
        db_session_factory=lambda: FakeDbSession(rows),
    )
    assert result["path_exists"] is True
    assert result["hop_count"] == 3
    assert result["path"] == ["eth:0xs", "eth:0a", "eth:0xb", "eth:0xt"]


def test_weighted_path_builds_graph_and_finds_path(fake_driver):
    rows = [
        transaction_row(1, "0xs", "0a"),
        transaction_row(2, "0a", "0xt"),
    ]
    result = service.weighted_path(
        fake_driver,
        "eth:0xs",
        "eth:0xt",
        weight="amount",
        db_session_factory=lambda: FakeDbSession(rows),
    )
    assert result["path_exists"] is True
    assert result["hop_count"] == 2
    assert isinstance(result["total_cost"], float)


def test_weighted_path_rejects_unknown_weight(fake_driver):
    with pytest.raises(ValueError):
        service.weighted_path(
            fake_driver, "eth:0xs", "eth:0xt", weight="unknown"
        )


def test_bfs_analysis_db_error_raises_graph_load_error(fake_driver):
    from graph.db_loader import GraphLoadError

    class FailingSession:
        def __enter__(self):
            from sqlalchemy.exc import SQLAlchemyError

            raise SQLAlchemyError("connection refused")

        def __exit__(self, *args):
            return False

    with pytest.raises(GraphLoadError):
        service.bfs_shortest_path(
            fake_driver,
            "eth:0xs",
            "eth:0xt",
            db_session_factory=lambda: FailingSession(),
        )