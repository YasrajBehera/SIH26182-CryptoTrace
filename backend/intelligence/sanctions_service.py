"""Criminal / sanctions intelligence service.

This service is entirely SEPARATE from the VASP attribution layer. VASP
attribution scores ("Binance 15.5/100 LOW") are transactional-association
scores; the criminal/sanctions intelligence here is a distinct,
well-labeled signal anchored to a curated public intelligence record. They
never merge: a sanctions match must never inflate a VASP score, and a VASP
score is never used as a criminal-risk determination.
"""

from __future__ import annotations

from typing import Optional

from intelligence.curated_sanctions import load_curated_sanctions_directory
from intelligence.sanctions_models import (
    SanctionsIntelligenceRecord,
    SanctionsLookup,
)


def sanctions_evidence_id(address: str, chain: str = "eth") -> str:
    """Deterministic evidence id for the sanctions_match record of an address.

    Idempotent across the risk service and the case service so a match can be
    re-asserted without duplicating the persisted evidence record.
    """
    import hashlib

    digest = hashlib.sha1(
        f"san:{chain}:{address}".lower().encode()
    ).hexdigest()[:12]
    return f"ev-san-{digest}"


def sanctions_analysis_id(address: str, chain: str = "eth") -> str:
    """Deterministic attribution/analysis id that groups sanctions records."""
    import hashlib

    digest = hashlib.sha1(
        f"san-analysis:{chain}:{address}".lower().encode()
    ).hexdigest()[:12]
    return f"san-{digest}"


class SanctionsIntelligenceService:
    def __init__(self, repository=None) -> None:
        # Loads the curated PUBLIC directory (the only sanctions reference).
        self._repo = repository or load_curated_sanctions_directory()

    @property
    def repository(self):
        return self._repo

    def lookup(
        self, address: str, chain: str = "eth"
    ) -> Optional[SanctionsIntelligenceRecord]:
        """Exact lookup by canonical address. Only the address itself can be
        matched; neighbours are never matched by proximity."""
        return self._repo.lookup_by_address(address.lower(), chain)

    def lookup_result(
        self, address: str, chain: str = "eth"
    ) -> SanctionsLookup:
        record = self.lookup(address, chain)
        return SanctionsLookup(
            address=address.lower(),
            chain=chain,
            matched=record is not None,
            level="high" if record else "unknown",
            record=record,
        )

    def is_exact_match(self, address: str, chain: str = "eth") -> bool:
        return self.lookup(address, chain) is not None