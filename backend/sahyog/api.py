"""SAHYOG referral API (DEMO flow; no live SAHYOG integration)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.audit.service import AuditService, get_audit_service_dep
from app.auth.deps import CurrentUser, require_permission
from cases.api import get_investigation_service_dep
from cases.service import InvestigationService
from sahyog.models import (
    HandoffRequest,
    SahyogReferralCreate,
    SahyogReferralOut,
    TriageRequest,
)
from sahyog.repository import make_sahyog_repository
from sahyog.service import (
    SahyogChainNotSupportedError,
    SahyogReferralNotFoundError,
    SahyogService,
)

router = APIRouter(prefix="/api/v1/sahyog", tags=["sahyog"])

DEMO_NOTICE = (
    "SAHYOG flow is a DEMO simulation. No live SAHYOG/LE intake connection is "
    "used; referrals are locally ingested and remain in the CryptoTrace system."
)


def get_sahyog_service_dep(
    repository=Depends(make_sahyog_repository),
) -> SahyogService:
    return SahyogService(repository=repository)


def _to_http(exc: BaseException) -> HTTPException:
    if isinstance(exc, SahyogReferralNotFoundError):
        return HTTPException(status_code=404, detail="Referral not found")
    if isinstance(exc, SahyogChainNotSupportedError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail="Unexpected error")


@router.get(
    "/referrals",
    response_model=list[SahyogReferralOut],
    responses={
        200: {"description": "Referrals listed"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def list_referrals(
    status: Optional[str] = Query(None, pattern="^(new|triaged|handed_off)$"),
    service: SahyogService = Depends(get_sahyog_service_dep),
    _current_user: CurrentUser = Depends(require_permission("investigation.read")),
):
    return service.list(status=status)


@router.get(
    "/referrals/{referral_id}",
    response_model=SahyogReferralOut,
    responses={
        200: {"description": "Referral retrieved"},
        404: {"description": "Referral not found"},
    },
)
def get_referral(
    referral_id: str = Path(...),
    service: SahyogService = Depends(get_sahyog_service_dep),
    _current_user: CurrentUser = Depends(require_permission("investigation.read")),
):
    try:
        return service.get(referral_id)
    except BaseException as exc:
        raise _to_http(exc)


@router.post(
    "/referrals",
    response_model=SahyogReferralOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Referral ingested (DEMO)"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def ingest_referral(
    payload: SahyogReferralCreate,
    service: SahyogService = Depends(get_sahyog_service_dep),
    audit_service: AuditService = Depends(get_audit_service_dep),
    _current_user: CurrentUser = Depends(require_permission("investigation.create")),
):
    result = service.ingest(payload)
    result.data_source = "demo"
    audit_service.record_event(
        user=_current_user.username,
        action="SAHYOG_INGEST",
        resource="sahyog_referral",
        resource_id=result.id,
        result="ingested",
    )
    return result


@router.post(
    "/referrals/{referral_id}/triage",
    response_model=SahyogReferralOut,
    responses={
        200: {"description": "Referral triaged (DEMO)"},
        404: {"description": "Referral not found"},
    },
)
def triage_referral(
    payload: TriageRequest,
    referral_id: str = Path(...),
    service: SahyogService = Depends(get_sahyog_service_dep),
    audit_service: AuditService = Depends(get_audit_service_dep),
    _current_user: CurrentUser = Depends(require_permission("investigation.update")),
):
    try:
        result = service.triage(referral_id, payload, _current_user)
        audit_service.record_event(
            user=_current_user.username,
            action="SAHYOG_TRIAGE",
            resource="sahyog_referral",
            resource_id=referral_id,
            result="triaged",
        )
        return result
    except BaseException as exc:
        raise _to_http(exc)


@router.post(
    "/referrals/{referral_id}/handoff",
    response_model=SahyogReferralOut,
    responses={
        200: {"description": "Referral handed off to a CryptoTrace investigation"},
        404: {"description": "Referral not found"},
        409: {"description": "Handoff not supported for this chain / state"},
    },
)
def handoff_referral(
    payload: HandoffRequest,
    referral_id: str = Path(...),
    service: SahyogService = Depends(get_sahyog_service_dep),
    investigation_service: InvestigationService = Depends(
        get_investigation_service_dep
    ),
    audit_service: AuditService = Depends(get_audit_service_dep),
    _current_user: CurrentUser = Depends(require_permission("investigation.update")),
):
    try:
        result = service.handoff(
            referral_id, payload, _current_user, investigation_service
        )
        audit_service.record_event(
            user=_current_user.username,
            action="SAHYOG_HANDOFF",
            resource="sahyog_referral",
            resource_id=referral_id,
            result=result.handoff_case_id or "no-case",
        )
        return result
    except BaseException as exc:
        raise _to_http(exc)


@router.get("/demo-notice")
def demo_notice(
    _current_user: CurrentUser = Depends(require_permission("investigation.read")),
):
    return {"notice": DEMO_NOTICE, "is_demo": True}