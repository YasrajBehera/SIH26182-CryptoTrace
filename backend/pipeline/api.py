from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.audit.service import AuditService, get_audit_service_dep
from app.auth.deps import CurrentUser, require_permission
from cases.api import get_investigation_service
from cases.service import CaseConflictError, CaseNotFoundError
from pipeline.models import InvestigationRequest, InvestigationResult
from pipeline.service import InvestigationPipeline

router = APIRouter(prefix="/api/v1/investigations", tags=["investigations"])

_pipeline = InvestigationPipeline()


@router.post(
    "/{address}/analyze",
    response_model=InvestigationResult,
    responses={
        200: {"description": "Investigation complete"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Investigation (case) not found"},
        409: {"description": "Analysis ran against a different wallet than the case"},
    },
)
def analyze_investigation(
    address: str = Path(...),
    chain: str = Query("eth"),
    limit: int | None = Query(None, ge=1, le=10000),
    case_id: Optional[str] = Query(
        None, description="Optional persisted investigation to attach results to"
    ),
    investigation_service=Depends(get_investigation_service),
    audit_service: AuditService = Depends(get_audit_service_dep),
    _current_user: CurrentUser = Depends(require_permission("wallet.analyze")),
):
    """Full pipeline: live/synthetic transfers -> graph -> attribution ->
    evidence. If ``case_id`` is supplied the analysis is ALSO bound to the
    persisted investigation (evidence, wallet summary, risk, candidates)."""
    request = InvestigationRequest(address=address, chain=chain, limit=limit)
    result = _pipeline.run(request)

    audit_service.record_event(
        user=_current_user.username,
        action="ANALYZE",
        resource="investigation",
        resource_id=address,
        result=f"{result.data_source}:{len(result.transactions) if result.transactions else result.transfers_ingested}",
    )

    if case_id:
        try:
            investigation_service.apply_analysis(
                case_id=case_id,
                address=result.address,
                analysis_id=result.analysis_id,
                data_source=result.data_source,
                candidates=[c.model_dump() for c in result.candidates],
                transactions=result.transactions,
                user=_current_user,
            )
        except CaseNotFoundError:
            raise HTTPException(status_code=404, detail="Investigation not found")
        except CaseConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        result.case_id = case_id

    return result