"""Investigation (case) management module."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

InvestigationStatus = Literal[
    "draft", "open", "investigating", "review", "escalated", "closed"
]
RiskLevel = Literal["critical", "high", "medium", "low", "unknown"]

_WALLET_PATTERN = r"^0x[a-fA-F0-9]{40}$"


class InvestigationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    primary_wallet: str = Field(..., pattern=_WALLET_PATTERN)
    network: str = "eth"
    priority: str = "normal"
    tags: List[str] = Field(default_factory=list)


class InvestigationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = None
    status: Optional[InvestigationStatus] = None
    priority: Optional[str] = None
    assigned_analyst: Optional[str] = Field(None, max_length=128)
    risk: Optional[RiskLevel] = None
    tags: Optional[List[str]] = None


class InvestigationOut(BaseModel):
    id: str
    name: str
    description: str = ""
    primary_wallet: str
    network: str = "eth"
    priority: str = "normal"
    risk: str = "unknown"
    status: str = "open"
    transactions: int = 0
    vasp_candidates: int = 0
    evidence_count: int = 0
    assigned_analyst: str = "Unassigned"
    created_by: int = 0
    latest_analysis_id: Optional[str] = None
    data_source: str = "demo"
    created_at: str
    updated_at: str
    tags: List[str] = Field(default_factory=list)
    is_demo: bool = True


class InvestigationListResponse(BaseModel):
    investigations: List[InvestigationOut] = Field(default_factory=list)
    total: int = 0
    source: str = "memory"


class ApplyAnalysisRequest(BaseModel):
    address: str
    analysis_id: str = Field(..., min_length=1)
    candidates: Optional[List[dict]] = None
    transactions: Optional[List[dict]] = None
    data_source: str = "demo"