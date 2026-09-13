"""M9 Investigator Intelligence Assistant: request/response schemas.

The assistant is a deterministic, evidence-grounded layer over the existing
investigation modules. It never runs new analysis, never fabricates data, and
never takes operational action on its own: it composes persisted, authorized
facts (cases, wallets, transactions, evidence, risk, reports) into structured
answers that an investigator must still review before acting.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

AssistantDataSource = Literal["live", "demo", "mixed", "unavailable"]


class AssistantQuickAction(BaseModel):
    """A one-click intent the interface offers the investigator."""

    id: str
    label: str
    description: str
    scope: Literal["case", "wallet"] = "case"
    requires_confirmation: bool = False


class AssistantRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    intent: Optional[str] = Field(None, max_length=64)
    case_id: Optional[str] = Field(None, max_length=64)
    wallet_address: Optional[str] = Field(None, max_length=64)
    chain: str = Field("eth", max_length=16)
    wallet2: Optional[str] = Field(None, max_length=64)


class AssistantSection(BaseModel):
    """A titled block of grounded observations in an assistant answer."""

    heading: str
    body: Optional[str] = None
    bullets: List[str] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)


class ReferralDraft(BaseModel):
    """A draft, non-submitted referral for investigator review.

    ``submission_state`` is always ``draft_for_review`` unless the SAHYOG
    connection is live; CryptoTrace never submits a referral autonomously.
    """

    title: str
    case_id: str
    primary_wallet: str
    chain: str
    summary: str
    evidence_ids: List[str] = Field(default_factory=list)
    transaction_hashes: List[str] = Field(default_factory=list)
    vasp_candidates: List[str] = Field(default_factory=list)
    risk_level: str = "unknown"
    risk_score: Optional[float] = None
    submission_state: Literal[
        "draft_for_review", "requires_sahyog_connection"
    ] = "requires_sahyog_connection"
    sahyog_status: str = "integration-ready"


class AssistantResponse(BaseModel):
    request_id: str
    intent: str
    title: str
    sections: List[AssistantSection] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    transaction_hashes: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    disclaimer: str
    data_source: AssistantDataSource = "unavailable"
    human_review_required: bool = True
    suggested_actions: List[AssistantQuickAction] = Field(default_factory=list)
    referral_draft: Optional[ReferralDraft] = None