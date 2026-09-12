"""Audit trail tests: repository, service, and API gating."""

from __future__ import annotations

import pytest

from app.security import create_signed_token

TEST_AUTH_SECRET = "test-auth-secret-0123456789abcdef"


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _token(username: str, role: str, user_id: str = "1") -> str:
    return create_signed_token(
        {"sub": user_id, "username": username, "role": role, "type": "access"},
        secret=TEST_AUTH_SECRET,
        ttl_seconds=3600,
    )


@pytest.fixture
def admin_headers() -> dict:
    return _bearer(_token("admin", "admin", "1"))


@pytest.fixture
def reviewer_headers() -> dict:
    return _bearer(_token("reviewer", "reviewer", "5"))


class TestAuditRepository:
    def test_create_and_list(self, memory_audit_repo):
        memory_audit_repo.create("alice", "LOGIN", "auth", "120", "success", ip="10.0.0.1")
        memory_audit_repo.create("bob", "EXPORT", "report", "r-9", "success")
        events = memory_audit_repo.list()
        assert len(events) == 2
        assert events[0].action == "EXPORT"  # newest first

    def test_filter_by_action(self, memory_audit_repo):
        memory_audit_repo.create("alice", "LOGIN", "auth", "", "success")
        memory_audit_repo.create("alice", "LOGOUT", "auth", "", "success")
        events = memory_audit_repo.list(action="logout")
        assert len(events) == 1
        assert events[0].action == "LOGOUT"

    def test_never_crash_on_bad_iso(self, memory_audit_repo):
        memory_audit_repo.create("alice", "LOGIN", "auth", "", "success")
        events = memory_audit_repo.list(from_iso="not-a-date", to_iso="also-bad")
        assert len(events) == 1
        assert events[0].action == "LOGIN"


class TestAuditService:
    def test_record_and_query(self, memory_audit_repo):
        from app.audit.service import AuditService
        from app.audit.models import AuditQuery

        svc = AuditService(repository=memory_audit_repo)
        svc.record_event("investigator", "ANALYZE", "wallet", "0xabc", "success", ip="10.1.2.3")
        out = svc.query(AuditQuery(action="analyze"))
        assert len(out) == 1
        assert out[0].resource_id == "0xabc"
        assert out[0].ip == "10.1.2.3"


class TestAuditApi:
    def test_unauth_access_rejected(self, auth_client):
        assert auth_client.get("/api/v1/audit").status_code == 401

    def test_invalid_token_rejected(self, auth_client):
        res = auth_client.get("/api/v1/audit", headers=_bearer("garbage-token"))
        assert res.status_code == 401

    def test_reviewer_lacks_audit_read(self, auth_client, reviewer_headers):
        res = auth_client.get("/api/v1/audit", headers=reviewer_headers)
        assert res.status_code == 403

    def test_admin_sees_login_events(self, auth_client, admin_headers):
        auth_client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "cryptotrace-demo"}
        )
        auth_client.post(
            "/api/v1/auth/login", json={"username": "nobody", "password": "cryptotrace-demo"}
        )
        res = auth_client.get("/api/v1/audit", headers=admin_headers)
        assert res.status_code == 200
        body = res.json()
        assert body["total"] >= 2
        assert body["source"] == "MemoryAuditLogRepository"
        actions = {e["action"] for e in body["events"]}
        assert "LOGIN" in actions

    def test_filter_by_result_denied(self, auth_client, admin_headers):
        auth_client.post(
            "/api/v1/auth/login", json={"username": "nobody", "password": "cryptotrace-demo"}
        )
        res = auth_client.get("/api/v1/audit", params={"result": "denied"}, headers=admin_headers)
        assert res.status_code == 200
        assert len(res.json()["events"]) >= 1
        assert all(e["result"] == "denied" for e in res.json()["events"])

    def test_audit_records_never_expose_passwords(self, auth_client, admin_headers, memory_audit_repo):
        login = auth_client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "cryptotrace-demo"}
        )
        assert login.status_code == 200
        # The internal audit repository must not hold a password anywhere.
        for event in memory_audit_repo.list():
            assert "password" not in (event.resource + event.resource_id + event.user).lower()
            assert "cryptotrace-demo" not in (event.resource + event.resource_id)