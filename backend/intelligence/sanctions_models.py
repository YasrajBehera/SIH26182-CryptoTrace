"""Criminal / sanctions intelligence record models.

These models describe CURATED PUBLIC INTELLIGENCE only. They carry the full
provenance (source, source type, match type, confidence) for every record so a
consumer can always tell exactly where an association came from. Nothing here
is a live OFAC (or any other) sanctions API integration.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SanctionsIntelligenceRecord(BaseModel):
    """One curated public sanctions/illicit intelligence entry.

    ``match_type`` is always ``exact_address`` for this layer: an association
    is only asserted when the FULL address matches. Proximity to a sanctioned
    address never lifts an unaffected wallet into this record set.
    """

    record_id: str
    chain: str = "eth"
    address: str
    entity: str
    classification: str = Field(
        ..., description="sanctioned / illicit"
    )
    source: str = "OFAC"
    match_type: str = "exact_address"
    confidence: str = "HIGH"
    source_type: str = "public_government"
    reference: Optional[str] = None
    notes: str = ""
    created_at: str = ""


class SanctionsLookup(BaseModel):
    """Response of the sanctions intelligence lookup endpoint.

    ``level`` is ``high`` only when an exact match exists in the curated set;
    otherwise ``unknown``. ``unknown`` means NOT ASSESSED — it never means
    "no criminal risk".
    """

    address: str
    chain: str
    matched: bool
    level: str
    data_source: str = "curated_public_intelligence"
    record: Optional[SanctionsIntelligenceRecord] = None