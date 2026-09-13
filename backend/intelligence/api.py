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
    data_source: str = Query(
        "demo", description="'live' checks the curated public VASP directory"
    ),
):
    return _service.lookup_address(address.lower(), chain, data_source=data_source)


@router.get("/vasp/names")
def list_vasp_names(chain: str = Query("eth")):
    # Live search operates against the curated PUBLIC directory (real entities).
    # Synthetic names are demo-only and never surface through the API.
    repo = _service.repository_for("live")
    names = set(repo.get_vasp_names_for_chain(chain))
    names.update(e.name for e in repo.get_all_entities())
    return {"chain": chain, "vasp_names": sorted(names)}
