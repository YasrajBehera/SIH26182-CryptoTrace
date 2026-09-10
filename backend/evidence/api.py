from typing import List

from fastapi import APIRouter, HTTPException, Path, Query

from evidence.models import EvidenceRecord
from evidence.service import EvidenceService

router = APIRouter(prefix="/api/v1/evidence", tags=["evidence"])

_service = None


def get_evidence_service() -> EvidenceService:
    global _service
    if _service is None:
        from attribution.api import get_attribution_service
        _service = get_attribution_service().evidence_service
    return _service


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
