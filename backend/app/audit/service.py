"""Audit trail service and FastAPI router.

Every sensitive action (login, logout, analyze, export, user admin) is
recorded here. The trail never stores passwords, tokens, or request bodies.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import Depends

from app.audit.models import AuditEventOut, AuditQuery
from app.audit.repository import (
    AuditLogRepository,
    make_audit_log_repository,
)


class AuditService:
    def __init__(self, repository: Optional[AuditLogRepository] = None) -> None:
        self._repo = repository or make_audit_log_repository()

    @property
    def repository(self) -> AuditLogRepository:
        return self._repo

    def record_event(
        self,
        user: str,
        action: str,
        resource: str,
        resource_id: str,
        result: str,
        ip: Optional[str] = None,
    ) -> str:
        """Record an event and return its row id (never logs secrets)."""
        event = self._repo.create(
            user=user,
            action=action.upper(),
            resource=resource,
            resource_id=resource_id,
            result=result,
            ip=ip,
        )
        return str(event.id)

    def query(self, q: AuditQuery) -> List[AuditEventOut]:
        rows = self._repo.list(
            user=q.user,
            action=q.action,
            resource=q.resource,
            result=q.result,
            from_iso=q.from_iso,
            to_iso=q.to_iso,
            limit=q.limit,
        )
        return [
            AuditEventOut(
                id=str(e.id),
                timestamp=e.timestamp.isoformat(),
                user=e.user,
                action=e.action,
                resource=e.resource,
                resource_id=e.resource_id,
                result=e.result,
                ip=e.ip,
            )
            for e in rows
        ]


_service: Optional[AuditService] = None


def get_audit_service() -> AuditService:
    global _service
    if _service is None:
        _service = AuditService()
    return _service


def get_audit_service_dep(
    repository: AuditLogRepository = Depends(make_audit_log_repository),
) -> AuditService:
    """FastAPI dependency so endpoints/tests can inject the audit repository."""
    return AuditService(repository=repository)