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


_transfers_service_instance = None


def _transfers_service():
    """Lazy BlockchainService wired to the wallet store (same store the
    ``GET /api/v1/wallets/{address}/transfers`` surface uses), so the live ML
    endpoint consumes the SAME canonical, deduplicated transfer set."""
    global _transfers_service_instance
    if _transfers_service_instance is None:
        from blockchain.service import BlockchainService
        from wallets.repository import make_wallet_repository

        service = BlockchainService()
        service.wallet_repository = make_wallet_repository()
        _transfers_service_instance = service
    return _transfers_service_instance


async def _live_transfers(address: str) -> list:
    """Real on-chain transfers for the wallet (persisted rows first, provider
    otherwise). Provider failure degrades to an empty set — the ML signal then
    honestly reports UNKNOWN / NOT ASSESSED rather than fabricating features."""
    try:
        result = await _transfers_service().get_wallet_transfers(
            address, limit=10000, offset=0
        )
        return list(result.transfers or [])
    except Exception:  # noqa: BLE001
        return []


@router.get(
    "/wallet/{address}/ml",
    responses={
        200: {
            "description": (
                "Live ML suspicious-wallet assessment. Status is always "
                "explicit: trained | not_trained | unavailable (UNKNOWN / NOT "
                "ASSESSED when required features cannot be computed). Never a "
                "determination of criminality and independent of the VASP score."
            )
        },
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
async def wallet_ml(
    address: str = Path(...),
    chain: str = Query("eth"),
    _current_user=Depends(require_permission("risk.read")),
) -> dict:
    """Compute the ML suspicious-wallet assessment for a wallet live.

    With no trained artifact this returns ``not_trained`` immediately (no
    provider call). With an artifact it consumes the wallet's REAL transfers,
    computes the canonical features, and returns a probability plus the top
    contributing features — or UNKNOWN / NOT ASSESSED when required features
    cannot be computed (never imputed).
    """
    from ml.service import MLRiskService

    service = MLRiskService()
    if service.model is None:
        return service.assess(address, chain, transfers=[])
    transfers = await _live_transfers(address)
    return service.assess(address, chain, transfers)