"""Audit trail API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.audit.models import AuditEventsResponse, AuditQuery
from app.audit.service import AuditService, get_audit_service_dep
from app.auth.deps import require_permission

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get(
    "",
    response_model=AuditEventsResponse,
    responses={
        200: {"description": "Audit events retrieved"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def list_audit_events(
    user: str | None = Query(None, max_length=64),
    action: str | None = Query(None, max_length=32),
    resource: str | None = Query(None, max_length=64),
    result: str | None = Query(None),
    from_iso: str | None = Query(None, alias="from"),
    to_iso: str | None = Query(None, alias="to"),
    limit: int = Query(200, ge=1, le=1000),
    service: AuditService = Depends(get_audit_service_dep),
    _current_user=Depends(require_permission("audit.read")),
) -> AuditEventsResponse:
    q = AuditQuery(
        user=user,
        action=action,
        resource=resource,
        result=result,
        from_iso=from_iso,
        to_iso=to_iso,
        limit=limit,
    )
    events = service.query(q)
    return AuditEventsResponse(
        events=events,
        total=len(events),
        source=service.repository.__class__.__name__,
    )