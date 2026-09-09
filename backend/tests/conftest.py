import pytest
from fastapi.testclient import TestClient


class FakeRecord(dict):
    pass


class FakeResult:
    def __init__(self, records=None):
        self._records = list(records or [])

    def __iter__(self):
        return iter(self._records)

    def single(self):
        return self._records[0] if self._records else None


class FakeSession:
    def __init__(self):
        self.queries = []
        self.wallet_count = 0
        self.transaction_count = 0
        self.no_ids = False
        self.bfs_records = [
            {"wallet_id": "eth:0xbb", "address": "0xbb", "chain": "eth", "depth": 1}
        ]
        self.dfs_records = [
            {"wallet_id": "eth:0xbb", "address": "0xbb", "chain": "eth"}
        ]
        self.flow_records = [
            {
                "source": "eth:0xsrc",
                "tx_id": "eth:0xabc",
                "tx_hash": "0xabc",
                "chain": "eth",
                "block_timestamp": 1704067200,
                "amount": "100",
                "target": "eth:0xwallet",
            }
        ]
        self.cluster_records = [
            {
                "community_id": 7,
                "wallets": [
                    {"wallet_id": "eth:0xaaaa", "address": "0xaaaa", "chain": "eth"},
                    {"wallet_id": "eth:0xbbbb", "address": "0xbbbb", "chain": "eth"},
                ],
            }
        ]
        self.path_record = {
            "nodes": [
                {
                    "node_id": 1,
                    "label": "Wallet",
                    "wallet_id": "eth:0xsrc",
                    "tx_id": None,
                    "address": "0xsrc",
                }
            ],
            "totalCost": 2.0,
        }

    def run(self, query, **params):
        self.queries.append((query, params))
        q = query.lower()

        if "gds.graph.exists" in q:
            return FakeResult([FakeRecord({"exists": True})])
        if "gds.graph.project" in q:
            return FakeResult([])
        if "count(w) as count" in q:
            return FakeResult([FakeRecord({"count": self.wallet_count})])
        if "count(t) as count" in q:
            return FakeResult([FakeRecord({"count": self.transaction_count})])
        if "merge (tx:transaction" in q:
            return FakeResult([])
        if "return id(w) as id" in q:
            return FakeResult([] if self.no_ids else [FakeRecord({"id": 1})])
        if "dijkstra" in q:
            return FakeResult([FakeRecord(self.path_record)])
        if "min(length(path))" in q:
            return FakeResult([FakeRecord(row) for row in self.bfs_records])
        if "apoc.path.expand" in q:
            return FakeResult([FakeRecord(row) for row in self.dfs_records])
        if "gds.wcc.stream" in q:
            return FakeResult([FakeRecord(row) for row in self.cluster_records])
        if "gds.louvain.stream" in q:
            return FakeResult([FakeRecord(row) for row in self.cluster_records])
        if "gds.leiden.stream" in q:
            return FakeResult([FakeRecord(row) for row in self.cluster_records])
        if "as block_timestamp" in q:
            return FakeResult([FakeRecord(row) for row in self.flow_records])
        return FakeResult([])

    def close(self):
        pass


class FakeDriver:
    def __init__(self, session=None):
        self._session = session or FakeSession()
        self.closed = False

    def session(self):
        return self._session

    def verify_connectedness(self):
        return True

    def close(self):
        self.closed = True


@pytest.fixture
def fake_session():
    return FakeSession()


@pytest.fixture
def fake_driver(fake_session):
    return FakeDriver(fake_session)


@pytest.fixture
def app_client(fake_driver):
    from app.main import app
    from graph.api import get_driver

    app.dependency_overrides[get_driver] = lambda: fake_driver
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()