"""Audit log repository.

Mirrors the user repository: a durable SQLAlchemy backend when Postgres is
reachable and a deterministic in-memory store otherwise (offline tests/demos).
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app import models
from app.db import SessionLocal, database_available


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO timestamp, silently ignoring malformed filters."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class AuditLogRepository:
    def create(
        self,
        user: str,
        action: str,
        resource: str,
        resource_id: str,
        result: str,
        ip: Optional[str] = None,
    ) -> models.AuditLog:
        raise NotImplementedError

    def list(
        self,
        *,
        user: Optional[str] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        result: Optional[str] = None,
        from_iso: Optional[str] = None,
        to_iso: Optional[str] = None,
        limit: int = 200,
    ) -> List[models.AuditLog]:
        raise NotImplementedError

    def count(self) -> int:
        raise NotImplementedError


class MemoryAuditLogRepository(AuditLogRepository):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: List[models.AuditLog] = []
        self._next_id = 1

    def create(
        self,
        user: str,
        action: str,
        resource: str,
        resource_id: str,
        result: str,
        ip: Optional[str] = None,
    ) -> models.AuditLog:
        with self._lock:
            event = models.AuditLog(
                id=self._next_id,
                timestamp=datetime.now(timezone.utc),
                user=user,
                action=action,
                resource=resource,
                resource_id=resource_id,
                result=result,
                ip=ip,
            )
            self._next_id += 1
            self._events.append(event)
            return event

    def list(
        self,
        *,
        user: Optional[str] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        result: Optional[str] = None,
        from_iso: Optional[str] = None,
        to_iso: Optional[str] = None,
        limit: int = 200,
    ) -> List[models.AuditLog]:
        needle_user = user.lower() if user else None
        needle_action = action.lower() if action else None
        needle_resource = resource.lower() if resource else None
        needle_result = result.lower() if result else None
        from_dt = _parse_dt(from_iso)
        to_dt = _parse_dt(to_iso)

        selected = []
        with self._lock:
            ordered = sorted(self._events, key=lambda e: e.timestamp, reverse=True)
        for e in ordered:
            if needle_user and e.user.lower() != needle_user:
                continue
            if needle_action and e.action.lower() != needle_action:
                continue
            if needle_resource and e.resource.lower() != needle_resource:
                continue
            if needle_result and e.result.lower() != needle_result:
                continue
            if from_dt and e.timestamp < from_dt:
                continue
            if to_dt and e.timestamp > to_dt:
                continue
            selected.append(e)
            if len(selected) >= limit:
                break
        return selected

    def count(self) -> int:
        with self._lock:
            return len(self._events)


class DbAuditLogRepository(AuditLogRepository):
    def create(
        self,
        user: str,
        action: str,
        resource: str,
        resource_id: str,
        result: str,
        ip: Optional[str] = None,
    ) -> models.AuditLog:
        event = models.AuditLog(
            user=user,
            action=action,
            resource=resource,
            resource_id=resource_id,
            result=result,
            ip=ip,
        )
        with SessionLocal() as session:
            session.add(event)
            session.commit()
            session.refresh(event)
        return event

    def list(
        self,
        *,
        user: Optional[str] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        result: Optional[str] = None,
        from_iso: Optional[str] = None,
        to_iso: Optional[str] = None,
        limit: int = 200,
    ) -> List[models.AuditLog]:
        from sqlalchemy import desc

        with SessionLocal() as session:
            query = session.query(models.AuditLog)
            if user:
                query = query.filter(models.AuditLog.user.ilike(user))
            if action:
                query = query.filter(models.AuditLog.action == action.upper())
            if resource:
                query = query.filter(models.AuditLog.resource.ilike(resource))
            if result:
                query = query.filter(models.AuditLog.result == result)
            from_dt = _parse_dt(from_iso)
            if from_dt:
                query = query.filter(models.AuditLog.timestamp >= from_dt)
            to_dt = _parse_dt(to_iso)
            if to_dt:
                query = query.filter(models.AuditLog.timestamp <= to_dt)
            return query.order_by(desc(models.AuditLog.timestamp)).limit(limit).all()

    def count(self) -> int:
        with SessionLocal() as session:
            return session.query(models.AuditLog).count()


_repository: Optional[AuditLogRepository] = None


def make_audit_log_repository() -> AuditLogRepository:
    global _repository
    if _repository is not None:
        return _repository
    _repository = DbAuditLogRepository() if database_available() else MemoryAuditLogRepository()
    return _repository