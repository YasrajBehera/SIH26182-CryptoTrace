"""Investigation (case) CRUD + case-bound analysis endpoints.

Route paths are chosen so they never collide with the pipeline's
``POST /api/v1/investigations/{address}/analyze``:
- ``POST   /api/v1/investigations``                 create a case
- ``GET    /api/v1/investigations``                 list cases
- ``GET    /api/v1/investigations/{case_id}``       read a case
- ``PATCH  /api/v1/investigations/{case_id}``       update a case
- ``DELETE /api/v1/investigations/{case_id}``       delete a case
- ``GET    /api/v1/investigations/{case_id}/risk``  case risk assessment
- ``POST   /api/v1/investigations/{case_id}/apply-analysis``
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from pydantic import BaseModel

from app.audit.service import AuditService, get_audit_service_dep
from app.auth.deps import require_permission
from cases.models import (
    ApplyAnalysisRequest,
    InvestigationContext,
    InvestigationCreate,
    InvestigationListResponse,
    InvestigationNoteCreate,
    InvestigationNoteListResponse,
    InvestigationNoteOut,
    InvestigationOut,
    InvestigationUpdate,
)
from cases.repository import InvestigationRepository, make_investigation_repository
from cases.service import (
    CaseAccessError,
    CaseConflictError,
    CaseNotFoundError,
    InvestigationService,
)
from evidence.api import get_evidence_service_dep
from risk.repository import make_risk_repository
from risk.service import RiskAssessment, RiskService
from wallets.repository import make_wallet_repository
from wallets.service import WalletService

router = APIRouter(prefix="/api/v1/investigations", tags=["investigations"])


def get_investigation_service_dep(
    repository: InvestigationRepository = Depends(make_investigation_repository),
    wallet_repository=Depends(make_wallet_repository),
    risk_repository=Depends(make_risk_repository),
    evidence_service=Depends(get_evidence_service_dep),
) -> InvestigationService:
    return InvestigationService(
        repository=repository,
        evidence_service=evidence_service,
        wallet_repository=wallet_repository,
        risk_repository=risk_repository,
    )


def _to_http(exc: BaseException) -> HTTPException:
    if isinstance(exc, CaseNotFoundError):
        return HTTPException(status_code=404, detail="Investigation not found")
    if isinstance(exc, CaseAccessError):
        return HTTPException(
            status_code=403, detail="Not allowed to modify this investigation"
        )
    if isinstance(exc, CaseConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail="Unexpected error")


@router.post(
    "",
    response_model=InvestigationOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Investigation created"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def create_case(
    payload: InvestigationCreate,
    service: InvestigationService = Depends(get_investigation_service_dep),
    audit_service: AuditService = Depends(get_audit_service_dep),
    current_user: CurrentUser = Depends(require_permission("investigation.create")),
):
    try:
        created = service.create(payload, current_user)
        audit_service.record_event(
            user=current_user.username,
            action="CASE_CREATE",
            resource="investigation",
            resource_id=created.id,
            result="created",
        )
        return created
    except BaseException as exc:
        raise _to_http(exc)


@router.get(
    "",
    response_model=InvestigationListResponse,
    responses={
        200: {"description": "Investigations listed"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def list_cases(
    status: Optional[str] = Query(None, description="Filter by case status"),
    q: Optional[str] = Query(None, description="Search name / wallet / description"),
    service: InvestigationService = Depends(get_investigation_service_dep),
    current_user: CurrentUser = Depends(require_permission("investigation.read")),
):
    return service.list(current_user, status=status, q=q)


@router.get(
    "/{case_id}",
    response_model=InvestigationOut,
    responses={
        200: {"description": "Investigation retrieved"},
        404: {"description": "Investigation not found"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_case(
    case_id: str = Path(...),
    service: InvestigationService = Depends(get_investigation_service_dep),
    current_user: CurrentUser = Depends(require_permission("investigation.read")),
):
    try:
        return service.get(case_id, current_user)
    except BaseException as exc:
        raise _to_http(exc)


@router.patch(
    "/{case_id}",
    response_model=InvestigationOut,
    responses={
        200: {"description": "Investigation updated"},
        404: {"description": "Investigation not found"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def update_case(
    payload: InvestigationUpdate,
    case_id: str = Path(...),
    service: InvestigationService = Depends(get_investigation_service_dep),
    audit_service: AuditService = Depends(get_audit_service_dep),
    current_user: CurrentUser = Depends(require_permission("investigation.update")),
):
    try:
        updated = service.update(case_id, payload, current_user)
        audit_service.record_event(
            user=current_user.username,
            action="CASE_UPDATE",
            resource="investigation",
            resource_id=case_id,
            result="updated",
        )
        return updated
    except BaseException as exc:
        raise _to_http(exc)


@router.delete(
    "/{case_id}",
    responses={
        200: {"description": "Investigation deleted"},
        404: {"description": "Investigation not found"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def delete_case(
    case_id: str = Path(...),
    service: InvestigationService = Depends(get_investigation_service_dep),
    audit_service: AuditService = Depends(get_audit_service_dep),
    current_user: CurrentUser = Depends(require_permission("investigation.update")),
):
    try:
        service.delete(case_id, current_user)
    except BaseException as exc:
        raise _to_http(exc)
    audit_service.record_event(
        user=current_user.username,
        action="CASE_DELETE",
        resource="investigation",
        resource_id=case_id,
        result="deleted",
    )
    return {"deleted": True, "case_id": case_id}


@router.get(
    "/{case_id}/notes",
    response_model=InvestigationNoteListResponse,
    responses={
        200: {"description": "Persisted analyst notes for the investigation"},
        404: {"description": "Investigation not found"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def list_case_notes(
    case_id: str = Path(...),
    service: InvestigationService = Depends(get_investigation_service_dep),
    audit_service: AuditService = Depends(get_audit_service_dep),
    current_user: CurrentUser = Depends(require_permission("investigation.read")),
):
    try:
        listing = service.notes(case_id, current_user)
    except BaseException as exc:
        raise _to_http(exc)
    audit_service.record_event(
        user=current_user.username,
        action="CASE_NOTE_LIST",
        resource="investigation",
        resource_id=case_id,
        result="listed",
    )
    return listing


@router.post(
    "/{case_id}/notes",
    response_model=InvestigationNoteOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Analyst note persisted"},
        404: {"description": "Investigation not found"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def create_case_note(
    payload: InvestigationNoteCreate,
    case_id: str = Path(...),
    service: InvestigationService = Depends(get_investigation_service_dep),
    audit_service: AuditService = Depends(get_audit_service_dep),
    current_user: CurrentUser = Depends(require_permission("investigation.update")),
):
    try:
        created = service.add_note(case_id, payload, current_user)
    except BaseException as exc:
        raise _to_http(exc)
    audit_service.record_event(
        user=current_user.username,
        action="CASE_NOTE_CREATE",
        resource="investigation",
        resource_id=case_id,
        result="created",
    )
    return created


@router.get(
    "/{case_id}/risk",
    response_model=RiskAssessment,
    responses={
        200: {"description": "Analytical risk assessment for the case wallet"},
        404: {"description": "Investigation not found"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def case_risk(
    case_id: str = Path(...),
    service: InvestigationService = Depends(get_investigation_service_dep),
    current_user: CurrentUser = Depends(require_permission("risk.read")),
):
    try:
        assessment = service.risk_for(case_id, current_user)
    except BaseException as exc:
        raise _to_http(exc)
    return assessment


@router.get(
    "/{case_id}/context",
    response_model=InvestigationContext,
    responses={
        200: {"description": "Investigation context aggregated"},
        404: {"description": "Investigation not found"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def case_context(
    case_id: str = Path(...),
    audit_service: AuditService = Depends(get_audit_service_dep),
    service: InvestigationService = Depends(get_investigation_service_dep),
    current_user: CurrentUser = Depends(require_permission("investigation.read")),
):
    """Aggregate the full investigation context (case, wallet summary, latest
    analysis, linked evidence, risk, reports) for the current user."""
    try:
        context = service.context(case_id, current_user)
    except BaseException as exc:
        raise _to_http(exc)
    audit_service.record_event(
        user=current_user.username,
        action="CASE_CONTEXT",
        resource="investigation",
        resource_id=case_id,
        result=context.scope,
    )
    return context


@router.post(
    "/{case_id}/apply-analysis",
    response_model=InvestigationOut,
    responses={
        200: {"description": "Analysis results attached to the investigation"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Analysis ran against a different wallet"},
    },
)
def apply_analysis_to_case(
    body: ApplyAnalysisRequest,
    case_id: str = Path(...),
    service: InvestigationService = Depends(get_investigation_service_dep),
    audit_service: AuditService = Depends(get_audit_service_dep),
    current_user: CurrentUser = Depends(require_permission("investigation.update")),
):
    try:
        updated = service.apply_analysis(
            case_id=case_id,
            address=body.address,
            analysis_id=body.analysis_id,
            data_source=body.data_source,
            candidates=body.candidates,
            transactions=body.transactions,
            user=current_user,
        )
        audit_service.record_event(
            user=current_user.username,
            action="CASE_APPLY_ANALYSIS",
            resource="investigation",
            resource_id=case_id,
            result=body.data_source,
        )
        return updated
    except BaseException as exc:
        raise _to_http(exc)


# Re-export so pipeline wiring can inject the same dependency.
get_investigation_service = get_investigation_service_dep