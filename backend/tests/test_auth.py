"""Auth API tests: login, logout, me, change-password, admin user CRUD, RBAC.

These run against the purpose-built auth TestClient (conftest.auth_client)
which uses deterministic in-memory repositories and a fixed signing secret, so
login-frequency behavior is stable and no external service is required.
"""

from __future__ import annotations

import pytest

from app.security import create_signed_token

TEST_AUTH_SECRET = "test-auth-secret-0123456789abcdef"


def _token(username: str, role: str, user_id: str = "1") -> str:
    return create_signed_token(
        {"sub": user_id, "username": username, "role": role, "type": "access"},
        secret=TEST_AUTH_SECRET,
        ttl_seconds=3600,
    )


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers() -> dict:
    return _bearer(_token("admin", "admin", "1"))


@pytest.fixture
def senior_headers() -> dict:
    return _bearer(_token("senior_investigator", "senior_investigator", "2"))


@pytest.fixture
def reviewer_headers() -> dict:
    return _bearer(_token("reviewer", "reviewer", "5"))


class TestLogin:
    def test_valid_credentials_return_token(self, auth_client):
        res = auth_client.post("/api/v1/auth/login", json={"username": "admin", "password": "cryptotrace-demo"})
        assert res.status_code == 200
        body = res.json()
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0
        assert body["access_token"]
        assert body["user"]["username"] == "admin"
        assert body["user"]["role"] == "admin"
        assert "password" not in body["user"]
        assert "password_hash" not in body["user"]

    def test_token_works_on_me(self, auth_client):
        login = auth_client.post(
            "/api/v1/auth/login", json={"username": "investigator", "password": "cryptotrace-demo"}
        ).json()
        res = auth_client.get("/api/v1/auth/me", headers=_bearer(login["access_token"]))
        assert res.status_code == 200
        assert res.json()["username"] == "investigator"

    def test_wrong_password_rejected(self, auth_client):
        res = auth_client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "super-wrong-password"}
        )
        assert res.status_code == 401
        assert "super-wrong-password" not in res.text.lower()

    def test_unknown_user_rejected(self, auth_client):
        res = auth_client.post(
            "/api/v1/auth/login", json={"username": "nobody", "password": "cryptotrace-demo"}
        )
        assert res.status_code == 401

    def test_disabled_account_rejected(self, auth_client, memory_user_repo):
        admin = memory_user_repo.get_by_username("admin")
        memory_user_repo.update_user(str(admin.id), is_active=False)
        res = auth_client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "cryptotrace-demo"}
        )
        assert res.status_code == 401

    def test_senior_investigator_role_seeded(self, auth_client):
        res = auth_client.post(
            "/api/v1/auth/login",
            json={"username": "senior_investigator", "password": "cryptotrace-demo"},
        )
        assert res.status_code == 200
        assert res.json()["user"]["role"] == "senior_investigator"


class TestMe:
    def test_me_without_token(self, auth_client):
        res = auth_client.get("/api/v1/auth/me")
        assert res.status_code == 401

    def test_me_with_garbage_token(self, auth_client):
        res = auth_client.get("/api/v1/auth/me", headers=_bearer("not-a-real-token"))
        assert res.status_code == 401

    def test_me_with_valid_token(self, auth_client, senior_headers):
        res = auth_client.get("/api/v1/auth/me", headers=senior_headers)
        assert res.status_code == 200
        assert res.json()["role"] == "senior_investigator"
        assert res.json()["is_active"] is True


class TestLogout:
    def test_logout_is_stateless_and_requires_auth(self, auth_client, admin_headers):
        res = auth_client.post("/api/v1/auth/logout", headers=admin_headers)
        assert res.status_code == 200
        assert res.json()["ok"] is True

    def test_logout_without_token_rejected(self, auth_client):
        assert auth_client.post("/api/v1/auth/logout").status_code == 401


class TestChangePassword:
    def test_change_password_then_login(self, auth_client, admin_headers):
        res = auth_client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "cryptotrace-demo", "new_password": "brand-new-password-99"},
            headers=admin_headers,
        )
        assert res.status_code == 200

        old = auth_client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "cryptotrace-demo"}
        )
        assert old.status_code == 401

        new = auth_client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "brand-new-password-99"}
        )
        assert new.status_code == 200

    def test_wrong_current_password_rejected(self, auth_client, admin_headers):
        res = auth_client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "not-current", "new_password": "brand-new-password-99"},
            headers=admin_headers,
        )
        assert res.status_code == 400

    def test_weak_new_password_rejected(self, auth_client, admin_headers):
        res = auth_client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "cryptotrace-demo", "new_password": "12345"},
            headers=admin_headers,
        )
        assert res.status_code == 422


class TestAdminUserCRUD:
    def test_list_users_requires_admin(self, auth_client, reviewer_headers):
        res = auth_client.get("/api/v1/admin/users", headers=reviewer_headers)
        assert res.status_code == 403

    def test_list_users_returns_seed(self, auth_client, admin_headers):
        res = auth_client.get("/api/v1/admin/users", headers=admin_headers)
        assert res.status_code == 200
        users = res.json()["users"]
        usernames = {u["username"] for u in users}
        assert {"admin", "senior_investigator", "investigator", "analyst", "reviewer"} <= usernames

    def test_create_user_and_login_with_it(self, auth_client, admin_headers):
        res = auth_client.post(
            "/api/v1/admin/users",
            json={
                "username": "newinvest",
                "display_name": "New Investigator",
                "email": "new@example.com",
                "role": "investigator",
                "title": "Field Investigator",
                "password": "fresh-password-123",
            },
            headers=admin_headers,
        )
        assert res.status_code == 201
        created = res.json()
        assert created["username"] == "newinvest"
        assert created["role"] == "investigator"
        assert "fresh-password-123" not in res.text

        login = auth_client.post(
            "/api/v1/auth/login", json={"username": "newinvest", "password": "fresh-password-123"}
        )
        assert login.status_code == 200
        assert (
            auth_client.get("/api/v1/auth/me", headers=_bearer(login.json()["access_token"])).status_code
            == 200
        )

    def test_create_user_duplicate_409(self, auth_client, admin_headers):
        res = auth_client.post(
            "/api/v1/admin/users",
            json={
                "username": "admin",
                "display_name": "Dupe",
                "role": "analyst",
                "password": "fresh-password-123",
            },
            headers=admin_headers,
        )
        assert res.status_code == 409

    def test_create_user_invalid_role_422(self, auth_client, admin_headers):
        res = auth_client.post(
            "/api/v1/admin/users",
            json={
                "username": "bogus",
                "display_name": "Bogus",
                "role": "superadmin",
                "password": "fresh-password-123",
            },
            headers=admin_headers,
        )
        assert res.status_code == 422

    def test_create_user_weak_password_422(self, auth_client, admin_headers):
        res = auth_client.post(
            "/api/v1/admin/users",
            json={
                "username": "weakpw",
                "display_name": "Weak",
                "role": "analyst",
                "password": "short",
            },
            headers=admin_headers,
        )
        assert res.status_code == 422

    def test_update_user(self, auth_client, admin_headers):
        users = auth_client.get("/api/v1/admin/users", headers=admin_headers).json()["users"]
        analyst = next(u for u in users if u["username"] == "analyst")
        res = auth_client.patch(
            f"/api/v1/admin/users/{analyst['id']}",
            json={"title": "Lead Intelligence Analyst", "role": "analyst"},
            headers=admin_headers,
        )
        assert res.status_code == 200
        assert res.json()["title"] == "Lead Intelligence Analyst"

    def test_disable_user_blocks_login(self, auth_client, admin_headers):
        users = auth_client.get("/api/v1/admin/users", headers=admin_headers).json()["users"]
        analyst = next(u for u in users if u["username"] == "analyst")
        res = auth_client.delete(f"/api/v1/admin/users/{analyst['id']}", headers=admin_headers)
        assert res.status_code == 200
        assert res.json()["is_active"] is False

        login = auth_client.post(
            "/api/v1/auth/login", json={"username": "analyst", "password": "cryptotrace-demo"}
        )
        assert login.status_code == 401


class TestRolesEndpoint:
    def test_roles_list_contains_six_roles(self, auth_client, admin_headers):
        res = auth_client.get("/api/v1/admin/users/roles", headers=admin_headers)
        assert res.status_code == 200
        roles = {r["role"] for r in res.json()}
        assert roles == {
            "admin",
            "senior_investigator",
            "investigator",
            "analyst",
            "reviewer",
            "read_only",
        }

    def test_senior_investigator_has_evidence_delete(self, auth_client):
        roles = auth_client.get(
            "/api/v1/admin/users/roles", headers=_bearer(_token("admin", "admin", "1"))
        ).json()
        senior = next(r for r in roles if r["role"] == "senior_investigator")
        assert "evidence.delete" in senior["permissions"]
        assert "user.manage" not in senior["permissions"]

    def test_roles_requires_user_manage(self, auth_client, reviewer_headers):
        assert (
            auth_client.get("/api/v1/admin/users/roles", headers=reviewer_headers).status_code == 403
        )