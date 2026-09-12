"""SAHYOG referral model: an ingest surface for complaint-derived referrals.

The module is a DEMO flow (no live SAHYOG connection), but every record keeps
honest provenance: status transitions (new -> triaged -> handed_off) are stored,
and handoffs reference the CryptoTrace case that was created.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

ReferralStatus = Literal["new", "triaged", "handed_off"]
ChainLiteral = Literal["eth", "btc"]

_SUSPECT_WALLET_PATTERN = r"^([0-9a-zA-Z]){25,64}$"


class TriageResult(BaseModel):
    risk: str = "unknown"
    wallet_age_months: float = 0.0
    exchange_exposed: bool = False
    prior_flags: int = 0
    recommendation: str = ""
    triaged_by: str = ""
    triaged_at: str = ""


class SahyogReferralCreate(BaseModel):
    fir_no: str = Field(..., min_length=1, max_length=64)
    victim_name: str = Field(..., min_length=1, max_length=128)
    amount_usdt: float = Field(..., ge=0.0)
    suspect_wallet: str = Field(..., pattern=_SUSPECT_WALLET_PATTERN)
    chain: ChainLiteral = "eth"
    reported_at: Optional[str] = None


class TriageRequest(BaseModel):
    risk: Optional[str] = None
    wallet_age_months: Optional[float] = None
    exchange_exposed: Optional[bool] = None
    prior_flags: Optional[int] = None
    recommendation: Optional[str] = None


class HandoffRequest(BaseModel):
    case_name: Optional[str] = None
    description: Optional[str] = None
    priority: str = "normal"


class SahyogReferralOut(BaseModel):
    id: str
    fir_no: str
    reported_at: Optional[str] = None
    victim_name: str
    amount_usdt: float
    suspect_wallet: str
    chain: str = "eth"
    status: str = "new"
    triage: Optional[dict] = None
    handoff_case_id: Optional[str] = None
    data_source: str = "demo"