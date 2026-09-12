"""Pydantic schemas for wallet summaries."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class WalletSummaryOut(BaseModel):
    address: str
    network: str
    first_seen: Optional[str] = None
    last_activity: Optional[str] = None
    transaction_count: int = 0
    incoming_volume: str = "0"
    outgoing_volume: str = "0"
    balance: Optional[str] = None
    risk: str = "unknown"
    risk_score: Optional[int] = None
    investigation_status: str = "not_analyzed"
    source: str = "memory"


class WalletSummaryIn(BaseModel):
    """Payload used to persist a computed wallet summary."""

    address: str
    chain: str
    first_seen: Optional[str] = None
    last_activity: Optional[str] = None
    transaction_count: int = 0
    incoming_volume: str = "0"
    outgoing_volume: str = "0"
    balance: Optional[str] = None
    risk: str = "unknown"
    risk_score: Optional[int] = None
    investigation_status: str = "analyzed"