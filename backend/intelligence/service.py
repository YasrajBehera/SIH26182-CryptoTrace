from typing import Optional

from intelligence.models import AddressIntelligence, VerificationStatus
from intelligence.repository import VASPRepository
from intelligence.synthetic_data import seed_synthetic_vasp_data


class VASPIntelligenceService:
    def __init__(self, repository: Optional[VASPRepository] = None) -> None:
        self._repo = repository or seed_synthetic_vasp_data()

    @property
    def repository(self) -> VASPRepository:
        return self._repo

    def lookup_address(
        self, address: str, chain: str
    ) -> AddressIntelligence:
        matches = self._repo.lookup_by_address(address, chain)
        if not matches:
            return AddressIntelligence(
                address=address,
                chain=chain,
                is_known_vasp=False,
                confidence=0.0,
            )

        best = max(matches, key=lambda m: m.confidence)
        entity = self._repo.get_entity(best.vasp_name)

        return AddressIntelligence(
            address=address,
            chain=chain,
            known_vasp=best.vasp_name,
            address_type=best.address_type.value,
            entity_type=entity.entity_type if entity else None,
            jurisdiction=entity.jurisdiction if entity else None,
            verification_status=best.verification_status.value,
            confidence=best.confidence,
            source=best.source,
            is_known_vasp=best.verification_status == VerificationStatus.VERIFIED,
            all_matches=matches,
        )
