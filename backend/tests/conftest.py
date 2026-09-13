import pytest
from fastapi.testclient import TestClient

import app.db as _app_db

# Keep the unit suite hermetic: the repositories choose a durable SQLAlchemy
# backend based on database_available(), which probes live Postgres. The test
# suite was written against the deterministic in-memory stores, so pin the
# decision to False before any test module can trigger a probe. The real
# backend still provisions and uses live Postgres at boot (see app.main).
_app_db._database_available = False


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
    from app.auth.deps import get_current_user
    from app.auth.repository import MemoryUserRepository, make_user_repository
    from app.auth.demo import DEMO_USERS
    from app.security import hash_password

    from cases.repository import (
        MemoryInvestigationRepository,
        make_investigation_repository,
    )
    from evidence.repository import EvidenceRepository, make_evidence_repository
    from risk.repository import MemoryRiskRepository, make_risk_repository
    from sahyog.repository import MemorySahyogRepository, make_sahyog_repository
    from wallets.repository import MemoryWalletRepository, make_wallet_repository

    # Keep the suite hermetic: even if a test's analyze call happens to reach
    # the live blockchain provider, the shared pipeline singleton must never
    # write to a real Neo4j instance.
    import pipeline.api as _pipeline_api
    from pipeline.service import InvestigationPipeline as _InvestigationPipeline

    _prev_pipeline = _pipeline_api._pipeline
    _pipeline_api._pipeline = _InvestigationPipeline(sync_to_neo4j=False)

    repo = MemoryUserRepository()
    for spec in DEMO_USERS:
        repo.create_user(
            username=spec["username"],
            display_name=spec["display_name"],
            email=spec.get("email", ""),
            role=spec["role"],
            title=spec.get("title", ""),
            password_hash=hash_password("cryptotrace-demo"),
            is_demo=True,
        )
    admin = repo.get_by_username("admin")

    app.dependency_overrides[get_driver] = lambda: fake_driver
    app.dependency_overrides[make_user_repository] = lambda: repo
    app.dependency_overrides[get_current_user] = lambda: admin
    # Fresh in-memory stores per test (one shared instance so requests within
    # a single test share state) keep the cases/wallets/risk/sahyog surfaces
    # hermetic while the suite still shares the attribution evidence singleton
    # (as existing pipeline tests expect).
    cases_repo = MemoryInvestigationRepository()
    wallets_repo = MemoryWalletRepository()
    risk_repo = MemoryRiskRepository()
    sahyog_repo = MemorySahyogRepository()
    app.dependency_overrides[make_investigation_repository] = lambda: cases_repo
    app.dependency_overrides[make_evidence_repository] = lambda: EvidenceRepository()
    app.dependency_overrides[make_wallet_repository] = lambda: wallets_repo
    app.dependency_overrides[make_risk_repository] = lambda: risk_repo
    app.dependency_overrides[make_sahyog_repository] = lambda: sahyog_repo
    client = TestClient(app)
    # Expose the injected in-memory repositories so API tests can seed state
    # through the same stores the endpoints read (drop-in for search/context).
    client._test_cases_repo = cases_repo
    client._test_wallets_repo = wallets_repo
    client._test_risk_repo = risk_repo
    client._test_sahyog_repo = sahyog_repo
    _clear_rate_limits(client)
    yield client
    _pipeline_api._pipeline = _prev_pipeline
    app.dependency_overrides.clear()


def _clear_rate_limits(client):
    """Reset the process-global in-memory rate limiter between tests.

    The RateLimitMiddleware is installed once per process on the shared app, so
    without a reset, requests across many API tests (all seen as the same
    client IP) would trip the fixed-window limits and make the suite order- and
    speed-dependent. A health probe builds the middleware stack; afterwards we
    unwrap it to reach the limiter and drop its hit log.
    """
    from app.middleware import RateLimitMiddleware

    client.get("/api/v1/health")
    stack = getattr(client.app, "middleware_stack", None)
    seen = set()
    node = stack
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        if isinstance(node, RateLimitMiddleware):
            node._hits.clear()
            return
        node = getattr(node, "app", None)


TEST_AUTH_SECRET = "test-auth-secret-0123456789abcdef"


@pytest.fixture(autouse=True)
def _pin_auth_secret():
    """Pin the token secret for every test so the dev-secret dotfile (and its
    module-level cache) is never consulted or created during the suite."""
    from app.config import settings

    prev = settings.auth_secret
    settings.auth_secret = TEST_AUTH_SECRET
    try:
        yield
    finally:
        settings.auth_secret = prev


@pytest.fixture
def memory_user_repo():
    """Seeded in-memory user repository with the scaffolding demo accounts."""
    from app.auth.repository import MemoryUserRepository
    from app.auth.demo import DEMO_USERS
    from app.security import hash_password

    repo = MemoryUserRepository()
    for spec in DEMO_USERS:
        repo.create_user(
            username=spec["username"],
            display_name=spec["display_name"],
            email=spec.get("email", ""),
            role=spec["role"],
            title=spec.get("title", ""),
            password_hash=hash_password("cryptotrace-demo"),
            is_demo=True,
        )
    return repo


@pytest.fixture
def memory_audit_repo():
    from app.audit.repository import MemoryAuditLogRepository

    return MemoryAuditLogRepository()


@pytest.fixture
def auth_client(memory_user_repo, memory_audit_repo):
    """Purpose-built TestClient with auth/admin/audit routers only.

    Built on a fresh FastAPI app (no global rate limiter) so login-frequency
    tests are deterministic, with all repositories switched to in-memory stores
    and a fixed token-signing secret.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.auth.api import router as auth_router
    from app.auth.api import admin_router as admin_users_router
    from app.audit.api import router as audit_router
    from app.auth.repository import make_user_repository
    from app.audit.repository import make_audit_log_repository
    from app.auth.deps import get_auth_secret
    from app.config import settings

    test_app = FastAPI(title="cryptotrace-auth-test")
    test_app.include_router(auth_router)
    test_app.include_router(admin_users_router)
    test_app.include_router(audit_router)
    test_app.dependency_overrides[make_user_repository] = lambda: memory_user_repo
    test_app.dependency_overrides[make_audit_log_repository] = lambda: memory_audit_repo
    test_app.dependency_overrides[get_auth_secret] = lambda: TEST_AUTH_SECRET

    prev_auth_secret = settings.auth_secret
    settings.auth_secret = TEST_AUTH_SECRET
    try:
        yield TestClient(test_app)
    finally:
        settings.auth_secret = prev_auth_secret


def make_test_token(username: str, role: str, user_id: str = "1") -> str:
    """Issue a signed access token matching the fixture test secret."""
    from app.security import create_signed_token

    return create_signed_token(
        {"sub": user_id, "username": username, "role": role, "type": "access"},
        secret=TEST_AUTH_SECRET,
        ttl_seconds=3600,
    )


@pytest.fixture
def admin_token() -> str:
    return make_test_token("admin", "admin")


@pytest.fixture
def investigator_token() -> str:
    return make_test_token("senior_investigator", "senior_investigator", "2")


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


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
        self.bfs_edge_records = [
            {
                "source": "eth:0xaa",
                "target": "eth:0xbb",
                "tx_id": "eth:0xabc",
                "tx_hash": "0xabc",
                "chain": "eth",
                "amount": "100",
                "timestamp": 1704067200,
            }
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
        if "-[:received]->(other:wallet)" in q:
            return FakeResult([FakeRecord(row) for row in self.bfs_records])
        if "src.wallet_id as source" in q:
            return FakeResult([FakeRecord(row) for row in self.bfs_edge_records])
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