"""Curated public sanctions / illicit intelligence directory.

This is a SMALL, MANUALLY CURATED set of public government sanctions/illicit
listings loaded as static reference data — NOT a live OFAC or any other
authoritative API integration. Every entry records its provenance (source,
source type, match type, confidence) so the frontend, assistant, risk model
and PDF can always state honestly how the association was derived.

Conventions of this layer:

- ``match_type`` is always ``exact_address``: a wallet is only flagged when the
  FULL canonical address matches a record. Neighbours of a matched wallet are
  NEVER flagged by proximity.
- The presence of a record asserts a MAPPED-sanctions association ("address
  matches a curated public sanctions/illicit intelligence record"), never an
  ownership claim ("this wallet definitely belongs to <entity>").
- Absence of a record means UNKNOWN / NOT ASSESSED — never "not criminal".

Public source references (for the curated entries, as published):
  - OFAC Sanctions List Search: https://sanctionssearch.ofac.treas.gov/
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from intelligence.sanctions_models import SanctionsIntelligenceRecord

# Canonical curated entries: (chain, address, entity, classification,
# source, match_type, confidence, source_type, reference, notes).
_RECORDS: Tuple[tuple, ...] = (
    (
        "eth",
        "0x098b716b8aaf21512996dc57eb0615e2383e2f96",
        "Lazarus Group",
        "sanctioned",
        "OFAC",
        "exact_address",
        "HIGH",
        "public_government",
        "https://sanctionssearch.ofac.treas.gov/",
        "Curated public sanctions/illicit listing associated with the Lazarus "
        "Group. Asserted as an exact-address match; not a live OFAC feed.",
    ),
)


class SanctionsIntelligenceRepository:
    """In-memory store for the curated sanctions directory (small static data)."""

    is_demo: bool = False

    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], SanctionsIntelligenceRecord] = {}

    def add(self, record: SanctionsIntelligenceRecord) -> None:
        key = (record.chain, record.address.lower())
        self._records[key] = record

    def lookup_by_address(
        self, address: str, chain: str
    ) -> Optional[SanctionsIntelligenceRecord]:
        return self._records.get((chain, address.lower()))

    def all_records(self) -> list[SanctionsIntelligenceRecord]:
        return sorted(
            self._records.values(), key=lambda r: r.address
        )


_loaded: Optional[SanctionsIntelligenceRepository] = None


def load_curated_sanctions_directory() -> SanctionsIntelligenceRepository:
    """Load the curated directory once per process (small, static, shared)."""
    global _loaded
    if _loaded is None:
        repo = SanctionsIntelligenceRepository()
        now = datetime.now(timezone.utc).isoformat()
        for (
            chain,
            address,
            entity,
            classification,
            source,
            match_type,
            confidence,
            source_type,
            reference,
            notes,
        ) in _RECORDS:
            repo.add(
                SanctionsIntelligenceRecord(
                    record_id=_record_id(chain, address),
                    chain=chain,
                    address=address.lower(),
                    entity=entity,
                    classification=classification,
                    source=source,
                    match_type=match_type,
                    confidence=confidence,
                    source_type=source_type,
                    reference=reference,
                    notes=notes,
                    created_at=now,
                )
            )
        _loaded = repo
    return _loaded


def _record_id(chain: str, address: str) -> str:
    import hashlib

    digest = hashlib.sha1(f"{chain}:{address}".encode()).hexdigest()[:12]
    return f"san-{digest}"