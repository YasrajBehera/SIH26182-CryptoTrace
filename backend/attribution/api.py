from fastapi import APIRouter, HTTPException

from attribution.models import AttributionRequest, AttributionResponse
from attribution.service import AttributionService

router = APIRouter(prefix="/api/v1/attribution", tags=["attribution"])

_service = None


def get_attribution_service() -> AttributionService:
    global _service
    if _service is None:
        _service = AttributionService()
    return _service


@router.post(
    "/analyze",
    response_model=AttributionResponse,
    responses={
        200: {"description": "Attribution analysis complete"},
        422: {"description": "Invalid request"},
    },
)
def analyze_attribution(request: AttributionRequest):
    return get_attribution_service().analyze(request)


@router.get("/weights")
def get_scoring_weights():
    w = get_attribution_service().scorer.weights
    return {
        "graph_proximity": w.graph_proximity,
        "known_address_match": w.known_address_match,
        "temporal_consistency": w.temporal_consistency,
        "transaction_flow": w.transaction_flow,
        "cluster_evidence": w.cluster_evidence,
        "disclaimer": (
            "Scores are analytical rankings, NOT proof of wallet ownership."
        ),
    }
