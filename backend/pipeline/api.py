from fastapi import APIRouter

from pipeline.models import InvestigationRequest, InvestigationResult
from pipeline.service import InvestigationPipeline

router = APIRouter(prefix="/api/v1/investigations", tags=["investigations"])

_pipeline = InvestigationPipeline()


@router.post(
    "/{address}/analyze",
    response_model=InvestigationResult,
    responses={
        200: {"description": "Investigation complete"},
    },
)
def analyze_investigation(
    address: str,
    chain: str = "eth",
    limit: int | None = None,
):
    """Full pipeline: synthetic transactions -> graph -> attribution -> evidence."""
    request = InvestigationRequest(address=address, chain=chain, limit=limit)
    return _pipeline.run(request)
