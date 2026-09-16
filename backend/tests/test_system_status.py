"""Authenticated system-status endpoint contract.

GET /api/v1/system/status is a cheap, authenticated per-component availability
report for the dashboard's System Status card. It must:
  - reject anonymous callers (401) — it is not a public health probe
  - return a fixed boolean key set once a valid session is presented
  - never lie: values are plain booleans resolved by a live check

The Neo4j driver creation and health probe are monkeypatched so the unit suite
stays hermetic (no live bolt:// connections).
"""


def test_system_status_requires_auth():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.get("/api/v1/system/status")
    assert resp.status_code == 401


def test_system_status_shape_when_authenticated(app_client, monkeypatch, fake_driver):
    from graph import neo4j_client
    from blockchain.service import BlockchainService

    async def _provider_healthy(_self, timeout=5.0):
        return True

    monkeypatch.setattr(neo4j_client, "create_driver", lambda *a, **k: fake_driver)
    monkeypatch.setattr(neo4j_client, "is_neo4j_healthy", lambda driver: True)
    # Provider probe is a live network call — pin it so the suite stays hermetic.
    monkeypatch.setattr(BlockchainService, "provider_health", _provider_healthy)

    resp = app_client.get("/api/v1/system/status")
    assert resp.status_code == 200

    body = resp.json()
    fields = {
        "backend",
        "auth",
        "postgres",
        "blockchain",
        "neo4j",
        "graph",
        "vasp",
        "report",
        "sahyog",
        "sahyog_production",
    }
    assert fields.issubset(body.keys())
    # Values are plain booleans — honest yes/no per component.
    assert all(isinstance(body[field], bool) for field in fields)
    # Serving an authenticated request implies both of these.
    assert body["backend"] is True
    assert body["auth"] is True
    # A healthy graph engine surfaces on both the neo4j and graph slots.
    assert body["neo4j"] is True
    assert body["graph"] is True
    # A live provider answer must report the blockchain slot up.
    assert body["blockchain"] is True
    # SAHYOG only reports a production connection when an API is configured.
    assert body["sahyog_production"] is False


def test_system_status_reports_down_graph_honestly(app_client, monkeypatch, fake_driver):
    from graph import neo4j_client
    from blockchain.service import BlockchainService

    async def _provider_unhealthy(_self, timeout=5.0):
        return False

    monkeypatch.setattr(neo4j_client, "create_driver", lambda *a, **k: fake_driver)
    monkeypatch.setattr(neo4j_client, "is_neo4j_healthy", lambda driver: False)
    monkeypatch.setattr(BlockchainService, "provider_health", _provider_unhealthy)

    resp = app_client.get("/api/v1/system/status")
    assert resp.status_code == 200

    body = resp.json()
    assert body["neo4j"] is False
    assert body["graph"] is False


def test_system_status_reports_down_provider_honestly(app_client, monkeypatch, fake_driver):
    """A configured key alone must not flip the blockchain slot on — only a
    provider that actually answers a probe does."""
    from graph import neo4j_client
    from blockchain.service import BlockchainService

    async def _provider_unhealthy(_self, timeout=5.0):
        return False

    monkeypatch.setattr(neo4j_client, "create_driver", lambda *a, **k: fake_driver)
    monkeypatch.setattr(neo4j_client, "is_neo4j_healthy", lambda driver: True)
    monkeypatch.setattr(BlockchainService, "provider_health", _provider_unhealthy)

    resp = app_client.get("/api/v1/system/status")
    assert resp.status_code == 200

    body = resp.json()
    assert body["blockchain"] is False