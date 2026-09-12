from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from app.audit.service import AuditService, get_audit_service_dep
from app.auth.deps import require_permission
from evidence.models import EvidenceRecord, EvidenceType
from evidence.service import EvidenceService

router = APIRouter(prefix="/api/v1/evidence", tags=["evidence"])

_service = None


def get_evidence_service() -> EvidenceService:
    global _service
    if _service is None:
        from attribution.api import get_attribution_service

        _service = get_attribution_service().evidence_service
    return _service


def get_evidence_service_dep() -> EvidenceService:
    return get_evidence_service()


class EvidenceCreateRequest(BaseModel):
    attribution_id: str = Field(..., min_length=1)
    investigation_id: Optional[str] = None
    evidence_type: EvidenceType
    address: str
    chain: str = "eth"
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    description: str = ""
    tx_hash: Optional[str] = None
    graph_path: Optional[List[str]] = None
    source: str = "manual"


@router.get(
    "/{evidence_id}",
    response_model=EvidenceRecord,
    responses={
        200: {"description": "Evidence record retrieved"},
        404: {"description": "Evidence not found"},
    },
)
def get_evidence(evidence_id: str = Path(..., description="Evidence ID")):
    record = get_evidence_service().get_evidence(evidence_id)
    if not record:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return record


@router.get(
    "/address/{address}",
    response_model=List[EvidenceRecord],
)
def get_evidence_for_address(
    address: str = Path(...),
    chain: str = Query("eth"),
):
    return get_evidence_service().get_evidence_for_address(address, chain)


@router.get("/attribution/{attribution_id}", response_model=List[EvidenceRecord])
def get_evidence_for_attribution(
    attribution_id: str = Path(...),
):
    return get_evidence_service().get_evidence_for_attribution(attribution_id)


@router.get(
    "/investigation/{investigation_id}",
    response_model=List[EvidenceRecord],
    responses={
        200: {"description": "Evidence records for a persisted case"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_evidence_for_investigation(
    investigation_id: str = Path(...),
    _current_user=Depends(require_permission("evidence.read")),
):
    return get_evidence_service().get_evidence_for_investigation(investigation_id)


@router.post(
    "",
    response_model=EvidenceRecord,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Evidence attached"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def create_evidence(
    body: EvidenceCreateRequest,
    audit_service: AuditService = Depends(get_audit_service_dep),
    _current_user=Depends(require_permission("evidence.create")),
):
    """Attach a manual evidence record to an attribution or a persisted case.

    Records are stored with full provenance; nothing is ever fabricated.
    """
    record = get_evidence_service().create_evidence(
        attribution_id=body.attribution_id,
        investigation_id=body.investigation_id,
        evidence_type=body.evidence_type,
        address=body.address,
        chain=body.chain,
        confidence=body.confidence,
        description=body.description,
        tx_hash=body.tx_hash,
        graph_path=body.graph_path,
        source=body.source,
        method="manual_ingest",
    )
    audit_service.record_event(
        user=_current_user.username,
        action="EVIDENCE_CREATE",
        resource="evidence",
        resource_id=record.evidence_id,
        result=body.evidence_type,
    )
    return record


@router.delete(
    "/{evidence_id}",
    responses={
        200: {"description": "Evidence deleted"},
        404: {"description": "Evidence not found"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def delete_evidence(
    evidence_id: str = Path(...),
    audit_service: AuditService = Depends(get_audit_service_dep),
    _current_user=Depends(require_permission("evidence.delete")),
):
    """Delete an evidence record (audited by this endpoint)."""
    removed = get_evidence_service().delete_evidence(evidence_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Evidence not found")
    audit_service.record_event(
        user=_current_user.username,
        action="EVIDENCE_DELETE",
        resource="evidence",
        resource_id=evidence_id,
        result="deleted",
    )
    return {"deleted": True, "evidence_id": evidence_id}