from graph import service
from graph.db_loader import GraphLoadError


def test_health_endpoint(app_client, fake_session):
    fake_session.wallet_count = 4
    fake_session.transaction_count = 9
    resp = app_client.get("/api/v1/graph/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "ok", "wallets": 4, "transactions": 9}


def test_sync_endpoint(app_client, monkeypatch):
    monkeypatch.setattr(service, "sync_from_postgres", lambda driver: {"synced": 3})
    resp = app_client.post("/api/v1/graph/sync")
    assert resp.status_code == 200
    assert resp.json() == {"synced": 3}


def test_graph_summary_endpoint(app_client, monkeypatch):
    monkeypatch.setattr(
        service,
        "build_graph",
        lambda driver: {"wallet_count": 4, "transaction_count": 9},
    )
    resp = app_client.get("/api/v1/graph/summary")
    assert resp.status_code == 200
    assert resp.json() == {"wallet_count": 4, "transaction_count": 9}


def test_graph_summary_endpoint_empty(app_client, monkeypatch):
    monkeypatch.setattr(
        service,
        "build_graph",
        lambda driver: {"wallet_count": 0, "transaction_count": 0},
    )
    resp = app_client.get("/api/v1/graph/summary")
    assert resp.status_code == 200
    assert resp.json() == {"wallet_count": 0, "transaction_count": 0}


def test_graph_summary_db_error_returns_503(app_client, monkeypatch):
    def raise_db_error(driver):
        raise GraphLoadError("Connection to database lost")

    monkeypatch.setattr(service, "build_graph", raise_db_error)
    resp = app_client.get("/api/v1/graph/summary")
    assert resp.status_code == 503
    assert resp.json() == {"detail": "Connection to database lost"}


def test_wallet_endpoint_invalid_wallet_id(app_client):
    resp = app_client.get("/api/v1/graph/wallets/notawallet/bfs?depth=1")
    assert resp.status_code == 422


def test_neighbors_endpoint(app_client):
    resp = app_client.get("/api/v1/graph/wallets/eth:0xaa/neighbors?depth=1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["wallet_id"] == "eth:0xaa"
    assert body["max_depth"] == 1
    assert body["nodes"][0]["depth"] == 1


def test_bfs_endpoint(app_client):
    resp = app_client.get("/api/v1/graph/wallets/eth:0xaa/bfs?depth=3")
    assert resp.status_code == 200
    assert resp.json()["max_depth"] == 3


def test_bfs_endpoint_includes_edges(app_client, fake_session):
    fake_session.bfs_edge_records = [
        {
            "source": "eth:0xaa",
            "target": "eth:0xbb",
            "tx_id": "eth:0xedge",
            "tx_hash": "0xedge",
            "chain": "eth",
            "amount": "100",
            "timestamp": 1704067200,
            "block_number": 20698121,
        }
    ]
    resp = app_client.get("/api/v1/graph/wallets/eth:0xaa/bfs?depth=3")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["edges"]) == 1
    assert body["edges"][0] == {
        "source": "eth:0xaa",
        "target": "eth:0xbb",
        "tx_id": "eth:0xedge",
        "tx_hash": "0xedge",
        "chain": "eth",
        "amount": "100",
        "timestamp": 1704067200,
        "block_number": 20698121,
    }


def test_neighbors_endpoint_includes_edges(app_client, fake_session):
    fake_session.bfs_edge_records = [
        {
            "source": "eth:0xaa",
            "target": "eth:0xbb",
            "tx_id": "eth:0xedge",
            "tx_hash": "0xedge",
            "chain": "eth",
            "amount": "50",
            "timestamp": 1704067200,
            "block_number": 20698121,
        }
    ]
    resp = app_client.get("/api/v1/graph/wallets/eth:0xaa/neighbors?depth=1")
    assert resp.status_code == 200
    assert len(resp.json()["edges"]) == 1
    assert resp.json()["edges"][0]["block_number"] == 20698121


def test_dfs_endpoint(app_client):
    resp = app_client.get("/api/v1/graph/wallets/eth:0xaa/dfs?depth=4")
    assert resp.status_code == 200
    assert resp.json()["max_depth"] == 4


def test_shortest_path_endpoint(app_client):
    resp = app_client.get(
        "/api/v1/graph/shortest-path?source=eth:0xsrc&target=eth:0xdest&weight=hops"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    assert body["nodes"][0]["label"] == "Wallet"


def test_shortest_path_invalid_weight(app_client):
    resp = app_client.get(
        "/api/v1/graph/shortest-path?source=eth:0xsrc&target=eth:0xdest&weight=value"
    )
    assert resp.status_code == 422


def test_bfs_path_endpoint(app_client, monkeypatch):
    monkeypatch.setattr(
        service,
        "bfs_shortest_path",
        lambda driver, source, target: {
            "source": "eth:0xs",
            "destination": "eth:0xt",
            "path": ["eth:0xs", "eth:0xa", "eth:0xt"],
            "hop_count": 2,
            "found": True,
        },
    )
    resp = app_client.get("/api/v1/graph/bfs-path?source=eth:0xs&target=eth:0xt")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "eth:0xs"
    assert body["destination"] == "eth:0xt"
    assert body["hop_count"] == 2
    assert body["found"] is True
    assert body["path"] == ["eth:0xs", "eth:0xa", "eth:0xt"]


def test_bfs_path_endpoint_no_path(app_client, monkeypatch):
    monkeypatch.setattr(
        service,
        "bfs_shortest_path",
        lambda driver, source, target: {
            "source": "eth:0xs",
            "destination": "eth:0xt",
            "path": [],
            "hop_count": None,
            "found": False,
        },
    )
    resp = app_client.get("/api/v1/graph/bfs-path?source=eth:0xs&target=eth:0xt")
    assert resp.status_code == 200
    assert resp.json()["found"] is False


def test_bfs_path_endpoint_missing_params(app_client):
    resp = app_client.get("/api/v1/graph/bfs-path?source=eth:0xs")
    assert resp.status_code == 422


def test_dfs_path_endpoint(app_client, monkeypatch):
    monkeypatch.setattr(
        service,
        "dfs_path",
        lambda driver, source, target: {
            "source": "eth:0xs",
            "destination": "eth:0xt",
            "path": ["eth:0xs", "eth:0xa", "eth:0b", "eth:0c", "eth:0xt"],
            "hop_count": 4,
            "found": True,
        },
    )
    resp = app_client.get("/api/v1/graph/dfs-path?source=eth:0xs&target=eth:0xt")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "eth:0xs"
    assert body["destination"] == "eth:0xt"
    assert body["hop_count"] == 4
    assert body["found"] is True
    assert body["path"] == ["eth:0xs", "eth:0xa", "eth:0b", "eth:0c", "eth:0xt"]


def test_dfs_path_endpoint_no_path(app_client, monkeypatch):
    monkeypatch.setattr(
        service,
        "dfs_path",
        lambda driver, source, target: {
            "source": "eth:0xs",
            "destination": "eth:0xt",
            "path": [],
            "hop_count": None,
            "found": False,
        },
    )
    resp = app_client.get("/api/v1/graph/dfs-path?source=eth:0xs&target=eth:0xt")
    assert resp.status_code == 200
    assert resp.json()["found"] is False


def test_dfs_path_endpoint_missing_params(app_client):
    resp = app_client.get("/api/v1/graph/dfs-path?source=eth:0xs")
    assert resp.status_code == 422


def test_shortest_path_hops_endpoint(app_client, monkeypatch):
    monkeypatch.setattr(
        service,
        "shortest_path_by_hops",
        lambda driver, source, target: {
            "source": "eth:0xs",
            "destination": "eth:0xt",
            "path": ["eth:0xs", "eth:0a", "eth:0xt"],
            "hop_count": 2,
            "path_exists": True,
        },
    )
    resp = app_client.get(
        "/api/v1/graph/shortest-path-hops?source=eth:0xs&target=eth:0xt"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "eth:0xs"
    assert body["destination"] == "eth:0xt"
    assert body["hop_count"] == 2
    assert body["path_exists"] is True
    assert body["path"] == ["eth:0xs", "eth:0a", "eth:0xt"]


def test_shortest_path_hops_endpoint_missing_params(app_client):
    resp = app_client.get("/api/v1/graph/shortest-path-hops?source=eth:0xs")
    assert resp.status_code == 422


def test_weighted_path_endpoint(app_client, monkeypatch):
    monkeypatch.setattr(
        service,
        "weighted_path",
        lambda driver, source, target, weight="hops": {
            "source": "eth:0xs",
            "destination": "eth:0xt",
            "path": ["eth:0xs", "eth:0a", "eth:0xt"],
            "total_cost": 200.0,
            "hop_count": 2,
            "path_exists": True,
        },
    )
    resp = app_client.get(
        "/api/v1/graph/weighted-path?source=eth:0xs&target=eth:0xt&weight=amount"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "eth:0xs"
    assert body["destination"] == "eth:0xt"
    assert body["total_cost"] == 200.0
    assert body["hop_count"] == 2
    assert body["path_exists"] is True


def test_weighted_path_endpoint_no_path(app_client, monkeypatch):
    monkeypatch.setattr(
        service,
        "weighted_path",
        lambda driver, source, target, weight="hops": {
            "source": "eth:0xs",
            "destination": "eth:0xt",
            "path": [],
            "total_cost": None,
            "hop_count": None,
            "path_exists": False,
        },
    )
    resp = app_client.get(
        "/api/v1/graph/weighted-path?source=eth:0xs&target=eth:0xt"
    )
    assert resp.status_code == 200
    assert resp.json()["path_exists"] is False


def test_weighted_path_endpoint_invalid_weight(app_client):
    resp = app_client.get(
        "/api/v1/graph/weighted-path?source=eth:0xs&target=eth:0xt&weight=value"
    )
    assert resp.status_code == 422


def test_temporal_flow_endpoint(app_client):
    resp = app_client.get("/api/v1/graph/wallets/eth:0xwallet/temporal-flow")
    assert resp.status_code == 200
    body = resp.json()
    assert body["direction"] == "all"
    assert len(body["flows"]) == 2


def test_fund_flow_endpoint(app_client, monkeypatch):
    monkeypatch.setattr(
        service,
        "fund_flow_analysis",
        lambda driver, source, target: {
            "source": "eth:0xs",
            "destination": "eth:0xt",
            "wallet_path": ["eth:0xs", "eth:0a", "eth:0xt"],
            "hop_count": 2,
            "transactions": [
                {
                    "tx_hash": "0x01",
                    "chain": "eth",
                    "sender": "eth:0xs",
                    "receiver": "eth:0a",
                    "amount": "100",
                    "timestamp": 100,
                }
            ],
            "found": True,
        },
    )
    resp = app_client.get(
        "/api/v1/graph/fund-flow?source=eth:0xs&target=eth:0xt"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "eth:0xs"
    assert body["destination"] == "eth:0xt"
    assert body["wallet_path"] == ["eth:0xs", "eth:0a", "eth:0xt"]
    assert body["hop_count"] == 2
    assert body["found"] is True
    assert body["transactions"][0]["sender"] == "eth:0xs"
    assert body["transactions"][0]["receiver"] == "eth:0a"


def test_fund_flow_endpoint_no_path(app_client, monkeypatch):
    monkeypatch.setattr(
        service,
        "fund_flow_analysis",
        lambda driver, source, target: {
            "source": "eth:0xs",
            "destination": "eth:0xt",
            "wallet_path": [],
            "hop_count": None,
            "transactions": [],
            "found": False,
        },
    )
    resp = app_client.get(
        "/api/v1/graph/fund-flow?source=eth:0xs&target=eth:0xt"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is False
    assert body["hop_count"] is None
    assert body["wallet_path"] == []
    assert body["transactions"] == []


def test_clusters_endpoint(app_client):
    resp = app_client.get(
        "/api/v1/graph/clusters?algorithm=louvain&min_community_size=2"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["algorithm"] == "louvain"
    assert body["communities"][0]["community_id"] == 7
    assert len(body["communities"][0]["wallets"]) == 2


def test_clusters_invalid_algorithm(app_client):
    resp = app_client.get("/api/v1/graph/clusters?algorithm=dbscan")
    assert resp.status_code == 422


def test_temporal_path_endpoint(app_client, monkeypatch):
    monkeypatch.setattr(
        service,
        "temporal_path_analysis",
        lambda driver, source, target: {
            "source": "eth:0xs",
            "destination": "eth:0xt",
            "path": ["eth:0xs", "eth:0a", "eth:0xt"],
            "edges": [
                {
                    "tx_hash": "0x01",
                    "chain": "eth",
                    "sender": "eth:0xs",
                    "receiver": "eth:0a",
                    "amount": "100",
                    "timestamp": 100,
                },
                {
                    "tx_hash": "0x02",
                    "chain": "eth",
                    "sender": "eth:0a",
                    "receiver": "eth:0xt",
                    "amount": "200",
                    "timestamp": 200,
                },
            ],
            "is_temporally_valid": True,
            "total_hops": 2,
            "found": True,
        },
    )
    resp = app_client.get("/api/v1/graph/temporal-path?source=eth:0xs&target=eth:0xt")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "eth:0xs"
    assert body["destination"] == "eth:0xt"
    assert body["path"] == ["eth:0xs", "eth:0a", "eth:0xt"]
    assert body["total_hops"] == 2
    assert body["found"] is True
    assert len(body["edges"]) == 2
    assert body["edges"][0]["sender"] == "eth:0xs"


def test_temporal_path_endpoint_no_path(app_client, monkeypatch):
    monkeypatch.setattr(
        service,
        "temporal_path_analysis",
        lambda driver, source, target: {
            "source": "eth:0xs",
            "destination": "eth:0xt",
            "path": [],
            "edges": [],
            "is_temporally_valid": False,
            "total_hops": None,
            "found": False,
        },
    )
    resp = app_client.get("/api/v1/graph/temporal-path?source=eth:0xs&target=eth:0xt")
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is False
    assert body["total_hops"] is None
    assert body["path"] == []
    assert body["edges"] == []


def test_bfs_path_endpoint_invalid_source(app_client):
    resp = app_client.get("/api/v1/graph/bfs-path?source=notawallet&target=eth:0xt")
    assert resp.status_code == 422


def test_bfs_path_endpoint_invalid_target(app_client):
    resp = app_client.get("/api/v1/graph/bfs-path?source=eth:0xs&target=0xt")
    assert resp.status_code == 422


def test_dfs_path_endpoint_invalid_source(app_client):
    resp = app_client.get("/api/v1/graph/dfs-path?source=notawallet&target=eth:0xt")
    assert resp.status_code == 422


def test_shortest_path_hops_endpoint_invalid_source(app_client):
    resp = app_client.get(
        "/api/v1/graph/shortest-path-hops?source=notawallet&target=eth:0xt"
    )
    assert resp.status_code == 422


def test_weighted_path_endpoint_invalid_source(app_client):
    resp = app_client.get(
        "/api/v1/graph/weighted-path?source=notawallet&target=eth:0xt"
    )
    assert resp.status_code == 422


def test_temporal_path_endpoint_invalid_source(app_client):
    resp = app_client.get(
        "/api/v1/graph/temporal-path?source=notawallet&target=eth:0xt"
    )
    assert resp.status_code == 422


def test_fund_flow_endpoint_invalid_source(app_client):
    resp = app_client.get("/api/v1/graph/fund-flow?source=notawallet&target=eth:0xt")
    assert resp.status_code == 422