from fastapi import APIRouter, HTTPException, Path, Query

from intelligence.models import AddressIntelligence
from intelligence.service import VASPIntelligenceService

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])

_service = VASPIntelligenceService()


@router.get(
    "/address/{address}",
    response_model=AddressIntelligence,
    responses={
        200: {"description": "Address intelligence retrieved"},
        422: {"description": "Invalid parameters"},
    },
)
def get_address_intelligence(
    address: str = Path(..., description="Wallet address to look up"),
    chain: str = Query("eth", description="Blockchain chain"),
):
    return _service.lookup_address(address.lower(), chain)


@router.get("/vasp/names")
def list_vasp_names(chain: str = Query("eth")):
    names = _service.repository.get_vasp_names_for_chain(chain)
    return {"chain": chain, "vasp_names": names}
