"""Authentication and user-administration service.

Implements the actual security rules:
- constant-time password verification
- password policy (stdlib only)
- PBKDF2 hashing before any storage
- signed-token issuance with a TTL
- RBAC user CRUD guarded by the caller (router-level permission deps)
- demo seeding from env or one-time random passwords (never stored plaintext)
"""

from __future__ import annotations

from typing import List, Optional

from app import models
from app.audit.service import AuditService, get_audit_service
from app.auth.demo import DEMO_USERS
from app.auth.models import (
    TokenResponse,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.auth.repository import (
    InvalidRoleError,
    UserNotFoundError,
    UserRepository,
    make_user_repository,
)
from app.auth.roles import ROLES, ROLE_PERMISSIONS
from app.config import settings
from app.security import (
    PasswordPolicyError,
    create_signed_token,
    hash_password,
    validate_password_policy,
    verify_password,
)


class AuthError(Exception):
    pass


class InvalidCredentialsError(AuthError):
    pass


class PasswordMismatchError(AuthError):
    pass


class DisabledAccountError(AuthError):
    pass


class UserService:
    def __init__(
        self,
        repository: Optional[UserRepository] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self._repo = repository or make_user_repository()
        self._audit = audit_service or get_audit_service()

    @property
    def repository(self) -> UserRepository:
        return self._repo

    def authenticate(self, username: str, password: str, ip: Optional[str] = None) -> TokenResponse:
        user = self._repo.get_by_username(username)
        if not user or not verify_password(user.password_hash, password):
            self._audit.record_event(
                user=username.strip().lower() or "unknown",
                action="LOGIN",
                resource="auth",
                resource_id="",
                result="denied",
                ip=ip,
            )
            raise InvalidCredentialsError("Invalid username or password.")

        if not user.is_active:
            self._audit.record_event(
                user=user.username,
                action="LOGIN",
                resource="auth",
                resource_id="",
                result="denied",
                ip=ip,
            )
            raise DisabledAccountError("This account is disabled.")

        token_ttl = settings.auth_token_ttl_minutes * 60
        token = create_signed_token(
            {
                "sub": str(user.id),
                "username": user.username,
                "role": user.role,
                "type": "access",
            },
            secret=settings.resolved_auth_secret(),
            ttl_seconds=token_ttl,
        )
        self._repo.touch_last_active(str(user.id))
        self._audit.record_event(
            user=user.username,
            action="LOGIN",
            resource="auth",
            resource_id=str(token_ttl),
            result="success",
            ip=ip,
        )
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=token_ttl,
            user=self.to_out(user),
        )

    def create_user(self, payload: UserCreate, is_demo: bool = False) -> UserOut:
        policy_error = validate_password_policy(payload.password, payload.username)
        if policy_error:
            raise PasswordPolicyError(policy_error)
        if payload.role not in ROLES:
            raise InvalidRoleError(payload.role)
        user = self._repo.create_user(
            username=payload.username,
            display_name=payload.display_name,
            email=payload.email,
            role=payload.role,
            title=payload.title,
            password_hash=hash_password(payload.password),
            is_demo=is_demo,
        )
        self._audit.record_event(
            user=user.username,
            action="CREATE",
            resource="user",
            resource_id=str(user.id),
            result="success",
        )
        return self.to_out(user)

    def list_users(self) -> List[UserOut]:
        return [self.to_out(u) for u in self._repo.list_users()]

    def get_user(self, user_id: str) -> models.User:
        user = self._repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return user

    def update_user(self, user_id: str, payload: UserUpdate) -> UserOut:
        if payload.role is not None and payload.role not in ROLES:
            raise InvalidRoleError(payload.role)
        user = self._repo.update_user(
            user_id,
            display_name=payload.display_name,
            email=payload.email,
            role=payload.role,
            title=payload.title,
            is_active=payload.is_active,
        )
        self._audit.record_event(
            user=user.username,
            action="UPDATE",
            resource="user",
            resource_id=str(user.id),
            result="success",
        )
        return self.to_out(user)

    def change_password(
        self,
        username: str,
        current_password: str,
        new_password: str,
    ) -> None:
        user = self._repo.get_by_username(username)
        if not user or not verify_password(user.password_hash, current_password):
            self._audit.record_event(
                user=username.lower(),
                action="UPDATE",
                resource="password",
                resource_id="",
                result="denied",
            )
            raise PasswordMismatchError("Current password is incorrect.")
        policy_error = validate_password_policy(new_password, username)
        if policy_error:
            raise PasswordPolicyError(policy_error)
        self._repo.update_user(
            str(user.id), password_hash=hash_password(new_password)
        )
        self._audit.record_event(
            user=user.username,
            action="UPDATE",
            resource="password",
            resource_id=str(user.id),
            result="success",
        )

    def roles(self) -> List[dict]:
        return [
            {"role": role, "permissions": sorted(ROLE_PERMISSIONS[role])}
            for role in sorted(ROLE_PERMISSIONS)
        ]

    def ensure_demo_seed(self, password: Optional[str] = None, reset: bool = False) -> dict:
        """Create the scaffolding demo users if none exist.

        ``password`` is normally None: the shared demo password then comes from
        ``DEMO_SEED_PASSWORD`` env, or a one-time random value is generated and
        returned so the operator can print it ONCE. No plaintext is ever stored.
        With ``reset=True`` existing demo accounts are re-hashed in place.
        """
        if self._repo.count() > 0 and not reset:
            return {"seeded": False, "reason": "users already exist", "password": None}
        resolved = password or settings.demo_seed_password or None
        generated = False
        if resolved is None:
            import secrets as _secrets

            resolved = "".join(
                _secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789")
                for _ in range(18)
            )
            generated = True

        for spec in DEMO_USERS:
            policy_error = validate_password_policy(resolved, spec["username"])
            if policy_error:
                raise PasswordPolicyError(policy_error)
            existing = self._repo.get_by_username(spec["username"])
            if existing:
                self._repo.update_user(str(existing.id), password_hash=hash_password(resolved))
            else:
                self._repo.create_user(
                    username=spec["username"],
                    display_name=spec["display_name"],
                    email=spec.get("email", ""),
                    role=spec["role"],
                    title=spec.get("title", ""),
                    password_hash=hash_password(resolved),
                    is_demo=True,
                )
        return {
            "seeded": True,
            "reason": "demo scaffolding",
            "password": resolved if generated else None,
            "generated": generated,
        }

    def to_out(self, user: models.User) -> UserOut:
        return UserOut(
            id=str(user.id),
            username=user.username,
            display_name=user.display_name,
            email=user.email,
            role=user.role,
            title=user.title,
            is_active=user.is_active,
            is_demo=user.is_demo,
            last_active_at=user.last_active_at.isoformat() if user.last_active_at else None,
        )


_authenticator: Optional[UserService] = None


def get_user_service() -> UserService:
    global _authenticator
    if _authenticator is None:
        _authenticator = UserService()
    return _authenticator