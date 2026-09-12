"""REST surface for analytical risk assessments."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.auth.deps import require_permission
from risk.repository import make_risk_repository
from risk.service import RiskAssessment, RiskService

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])


def get_risk_service_dep(repository=Depends(make_risk_repository)) -> RiskService:
    return RiskService(repository=repository)


@router.get(
    "/wallet/{address}",
    response_model=RiskAssessment,
    responses={
        200: {"description": "Latest analytical risk for a wallet"},
        404: {"description": "No assessment stored for this wallet yet"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def wallet_risk(
    address: str = Path(...),
    chain: str = Query("eth"),
    service: RiskService = Depends(get_risk_service_dep),
    _current_user=Depends(require_permission("risk.read")),
):
    latest = service.get_for_wallet(address, chain)
    if latest is None:
        raise HTTPException(
            status_code=404,
            detail="No analytical risk assessment stored for this wallet yet. "
            "Run POST /api/v1/investigations/{address}/analyze first.",
        )
    return latest