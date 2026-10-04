from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from attribution.models import AttributionCandidate, Confidence
from intelligence.models import AddressIntelligence

#: Explicit data-source / status vocabulary. The UI renders these verbatim so a
#: synthetic investigation can never be mistaken for a live one.
STATUS_LIVE = "LIVE"
STATUS_LIVE_PARTIAL = "LIVE_PARTIAL"
STATUS_DEMO = "DEMO"
STATUS_NOT_CONFIGURED = "NOT_CONFIGURED"
STATUS_LIVE_DATA_UNAVAILABLE = "LIVE_DATA_UNAVAILABLE"
STATUS_UNSUPPORTED_CHAIN = "UNSUPPORTED_CHAIN"
STATUS_INVALID_ADDRESS = "INVALID_ADDRESS"
STATUS_NO_DATA = "NO_DATA"

#: Investigation modes.
#: ``live`` - real chain data only; failure is an honest error, never synthetic.
#: ``demo`` - synthetic data only; real chain data is not fetched.
#: ``auto`` - try live, and if unavailable say so explicitly in
#:             ``limitations`` before serving clearly-labelled synthetic data.
MODE_LIVE = "live"
MODE_DEMO = "demo"
MODE_AUTO = "auto"
INVESTIGATION_MODES = (MODE_LIVE, MODE_DEMO, MODE_AUTO)


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

    # ---- Added for honest multi-chain / provenance reporting ----------------
    # All defaulted so every existing consumer keeps working unchanged.
    status: str = Field(
        STATUS_DEMO, description="LIVE | LIVE_PARTIAL | DEMO | NOT_CONFIGURED | ..."
    )
    provider: str = Field("", description="Transport that produced the data, e.g. alchemy")
    message: str = Field("", description="Human-readable outcome, always populated")
    limitations: List[str] = Field(
        default_factory=list,
        description="What this result does not cover. Never empty for partial data.",
    )
    mode: str = Field(MODE_AUTO, description="Investigation mode that produced this result")
    live_status: str = Field(
        "",
        description="Outcome of the live-provider attempt: LIVE | LIVE_PARTIAL | "
        "NO_DATA | NOT_CONFIGURED | LIVE_DATA_UNAVAILABLE | UNSUPPORTED_CHAIN. "
        "Populated even when synthetic data was substituted, so the UI can "
        "show why live data is missing.",
    )