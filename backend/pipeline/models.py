from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from attribution.models import AttributionCandidate, Confidence
from intelligence.models import AddressIntelligence


class InvestigationRequest(BaseModel):
    address: str = Field(..., description="Wallet address to investigate")
    chain: str = Field("eth", description="Blockchain chain")
    limit: Optional[int] = Field(
        None, ge=1, le=10000, description="Cap on transfers to ingest"
    )


class InvestigationResult(BaseModel):
    address: str
    chain: str
    data_source: str = "demo"
    transfers_ingested: int = 0
    graph_nodes: int = 0
    graph_edges: int = 0
    address_intelligence: Optional[AddressIntelligence] = None
    candidates: List[AttributionCandidate] = Field(default_factory=list)
    analysis_id: Optional[str] = None
    evidence_count: int = 0
    case_id: Optional[str] = None
    transactions: List[dict] = Field(default_factory=list)
    disclaimer: str = (
        "This score is an analytical ranking heuristic. "
        "It is NOT proof of wallet ownership or VASP association."
    )
