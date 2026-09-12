"""User repository.

Two interchangeable backends:

- ``DbUserRepository``  - SQLAlchemy over the ``users`` table (durable).
- ``MemoryUserRepository`` - deterministic in-memory store used offline
  (tests, demos, no Postgres). Records are flagged ``is_demo=True``.

``make_user_repository()`` probes the database once and returns the durable
backend when Postgres is reachable, otherwise the in-memory one. This mirrors
the existing evidence/intelligence repository pattern while leaving the real
schema ready for production.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.exc import IntegrityError

from app import models
from app.auth.roles import ROLES
from app.db import SessionLocal, database_available


class DuplicateUserError(Exception):
    def __init__(self, username: str) -> None:
        super().__init__(f"Username is already taken: {username}")
        self.username = username


class UserNotFoundError(Exception):
    pass


class InvalidRoleError(ValueError):
    def __init__(self, role: str) -> None:
        super().__init__(f"Unknown role: {role}")
        self.role = role


class UserRepository:
    """Interface shared by the memory and database backends."""

    def create_user(
        self,
        username: str,
        display_name: str,
        email: str,
        role: str,
        title: str,
        password_hash: str,
        is_demo: bool = False,
    ) -> models.User:
        raise NotImplementedError

    def get_by_id(self, user_id: str) -> Optional[models.User]:
        raise NotImplementedError

    def get_by_username(self, username: str) -> Optional[models.User]:
        raise NotImplementedError

    def list_users(self) -> List[models.User]:
        raise NotImplementedError

    def update_user(
        self,
        user_id: str,
        *,
        display_name: Optional[str] = None,
        email: Optional[str] = None,
        role: Optional[str] = None,
        title: Optional[str] = None,
        password_hash: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> models.User:
        raise NotImplementedError

    def touch_last_active(self, user_id: str) -> None:
        raise NotImplementedError

    def count(self) -> int:
        raise NotImplementedError


class MemoryUserRepository(UserRepository):
    """Thread-safe in-memory store (offline/tests/demo)."""

    def __init__(self) -> None:
        # RLock: helper methods (_assign_id, get_by_id) are called from within
        # locked public methods, so the lock must be reentrant.
        self._lock = threading.RLock()
        self._by_id: Dict[int, models.User] = {}
        self._by_username: Dict[str, models.User] = {}
        self._next_id = 1

    def _assign_id(self, user: models.User) -> models.User:
        with self._lock:
            user.id = self._next_id
            self._next_id += 1
        return user

    def create_user(
        self,
        username: str,
        display_name: str,
        email: str,
        role: str,
        title: str,
        password_hash: str,
        is_demo: bool = False,
    ) -> models.User:
        key = username.strip().lower()
        if not key:
            raise ValueError("username must not be empty")
        if role not in ROLES:
            raise InvalidRoleError(role)
        user = models.User(
            username=key,
            display_name=(display_name or key).strip(),
            email=(email or "").strip(),
            role=role,
            title=(title or "").strip(),
            password_hash=password_hash,
            is_active=True,
            is_demo=is_demo,
            created_at=datetime.now(timezone.utc),
        )
        with self._lock:
            if key in self._by_username:
                raise DuplicateUserError(key)
            self._assign_id(user)
            self._by_username[key] = user
            self._by_id[user.id] = user
        return user

    def get_by_id(self, user_id: str) -> Optional[models.User]:
        with self._lock:
            return self._by_id.get(int(user_id))

    def get_by_username(self, username: str) -> Optional[models.User]:
        with self._lock:
            return self._by_username.get(username.strip().lower())

    def list_users(self) -> List[models.User]:
        with self._lock:
            return sorted(self._by_username.values(), key=lambda u: u.username)

    def update_user(
        self,
        user_id: str,
        *,
        display_name: Optional[str] = None,
        email: Optional[str] = None,
        role: Optional[str] = None,
        title: Optional[str] = None,
        password_hash: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> models.User:
        user = self.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        if role is not None and role not in ROLES:
            raise InvalidRoleError(role)
        if display_name is not None:
            user.display_name = display_name
        if email is not None:
            user.email = email
        if role is not None:
            user.role = role
        if title is not None:
            user.title = title
        if password_hash is not None:
            user.password_hash = password_hash
        if is_active is not None:
            user.is_active = is_active
        return user

    def touch_last_active(self, user_id: str) -> None:
        user = self.get_by_id(user_id)
        if user:
            user.last_active_at = datetime.now(timezone.utc)

    def count(self) -> int:
        with self._lock:
            return len(self._by_id)


class DbUserRepository(UserRepository):
    """Durable SQLAlchemy implementation over the ``users`` table."""

    def create_user(
        self,
        username: str,
        display_name: str,
        email: str,
        role: str,
        title: str,
        password_hash: str,
        is_demo: bool = False,
    ) -> models.User:
        key = username.strip().lower()
        if not key:
            raise ValueError("username must not be empty")
        if role not in ROLES:
            raise InvalidRoleError(role)
        user = models.User(
            username=key,
            display_name=(display_name or key).strip(),
            email=(email or "").strip(),
            role=role,
            title=(title or "").strip(),
            password_hash=password_hash,
            is_active=True,
            is_demo=is_demo,
        )
        with SessionLocal() as session:
            session.add(user)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise DuplicateUserError(key) from exc
            session.refresh(user)
        return user

    def _load(self, user_id: str) -> Optional[List[models.User]]:
        with SessionLocal() as session:
            return session.query(models.User).filter(models.User.id == int(user_id)).all()

    def get_by_id(self, user_id: str) -> Optional[models.User]:
        rows = self._load(user_id)
        return rows[0] if rows else None

    def get_by_username(self, username: str) -> Optional[models.User]:
        with SessionLocal() as session:
            return (
                session.query(models.User)
                .filter(models.User.username == username.strip().lower())
                .first()
            )

    def list_users(self) -> List[models.User]:
        with SessionLocal() as session:
            return session.query(models.User).order_by(models.User.username).all()

    def update_user(
        self,
        user_id: str,
        *,
        display_name: Optional[str] = None,
        email: Optional[str] = None,
        role: Optional[str] = None,
        title: Optional[str] = None,
        password_hash: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> models.User:
        with SessionLocal() as session:
            user = session.query(models.User).filter(models.User.id == int(user_id)).first()
            if not user:
                raise UserNotFoundError(user_id)
            if role is not None and role not in ROLES:
                raise InvalidRoleError(role)
            if display_name is not None:
                user.display_name = display_name
            if email is not None:
                user.email = email
            if role is not None:
                user.role = role
            if title is not None:
                user.title = title
            if password_hash is not None:
                user.password_hash = password_hash
            if is_active is not None:
                user.is_active = is_active
            session.commit()
            session.refresh(user)
            return user

    def touch_last_active(self, user_id: str) -> None:
        with SessionLocal() as session:
            session.query(models.User).filter(models.User.id == int(user_id)).update(
                {"last_active_at": datetime.now(timezone.utc)}
            )
            session.commit()

    def count(self) -> int:
        with SessionLocal() as session:
            return session.query(models.User).count()


_repository: Optional[UserRepository] = None


def make_user_repository() -> UserRepository:
    """Return a process-wide repository, preferring the durable backend."""
    global _repository
    if _repository is not None:
        return _repository
    _repository = DbUserRepository() if database_available() else MemoryUserRepository()
    return _repository