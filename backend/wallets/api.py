"""Wallet summary API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path

from app.auth.deps import require_permission
from wallets.models import WalletSummaryOut
from wallets.repository import WalletRepository, make_wallet_repository
from wallets.service import WalletService

router = APIRouter(prefix="/api/v1/wallets", tags=["wallets"])

_WALLET_ADDRESS_PATTERN = r"^0x[a-fA-F0-9]{40}$"


def get_wallet_service_dep(
    repository: WalletRepository = Depends(make_wallet_repository),
) -> WalletService:
    return WalletService(repository=repository)


@router.get(
    "/{address}/summary",
    response_model=WalletSummaryOut,
    responses={
        200: {"description": "Wallet summary retrieved"},
        404: {"description": "No data recorded for this wallet"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def wallet_summary(
    address: str = Path(..., pattern=_WALLET_ADDRESS_PATTERN),
    chain: str = "eth",
    service: WalletService = Depends(get_wallet_service_dep),
    _current_user=Depends(require_permission("wallet.read")),
) -> WalletSummaryOut:
    """Return the persisted summary for a wallet that has been analyzed.

    Only data that exists in the store is reported. A wallet that was never
    ingested returns 404 rather than fabricated live figures.
    """
    summary = service.summarize(address.lower(), chain)
    if summary is None:
        raise HTTPException(
            status_code=404,
            detail="No persisted data for this wallet yet. "
            "Run an investigation to populate its summary.",
        )
    return summary