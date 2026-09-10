from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ScoreBreakdown(BaseModel):
    graph_proximity: float = Field(0.0, ge=0.0, le=100.0)
    known_address_match: float = Field(0.0, ge=0.0, le=100.0)
    temporal_consistency: float = Field(0.0, ge=0.0, le=100.0)
    transaction_flow: float = Field(0.0, ge=0.0, le=100.0)
    cluster_evidence: float = Field(0.0, ge=0.0, le=100.0)


class AttributionCandidate(BaseModel):
    address: str
    chain: str
    vasp_name: str
    score: float = Field(0.0, ge=0.0, le=100.0)
    confidence: Confidence = Confidence.LOW
    evidence_ids: List[str] = Field(default_factory=list)
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    explanation: List[str] = Field(default_factory=list)


class AttributionRequest(BaseModel):
    address: str = Field(..., description="Wallet address to analyze")
    chain: str = Field("eth", description="Blockchain chain")
    graph_data: Optional[Dict] = Field(
        None,
        description="Graph analysis results from Member 2 (neighbors, paths, clusters)",
    )


class AttributionResponse(BaseModel):
    address: str
    chain: str
    candidates: List[AttributionCandidate] = Field(default_factory=list)
    analysis_id: str
    timestamp: str
    disclaimer: str = (
        "This score is an analytical ranking heuristic. "
        "It is NOT proof of wallet ownership or VASP association."
    )
