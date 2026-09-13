from typing import Optional

from intelligence.curated_directory import load_curated_vasp_directory
from intelligence.models import AddressIntelligence, VerificationStatus
from intelligence.repository import VASPRepository
from intelligence.synthetic_data import seed_synthetic_vasp_data

# Curated public directory is loaded once per process (small, static reference
# data) and shared across service instances.
_CURATED_REPO: Optional[VASPRepository] = None


class VASPIntelligenceService:
    def __init__(self, repository: Optional[VASPRepository] = None) -> None:
        # Default repository is the synthetic seed: demo/tests stay hermetic.
        self._repo = repository or seed_synthetic_vasp_data()

    @property
    def repository(self) -> VASPRepository:
        return self._repo

    @property
    def curated_repository(self) -> VASPRepository:
        """The curated PUBLIC VASP directory (real, documented addresses)."""
        global _CURATED_REPO
        if _CURATED_REPO is None:
            _CURATED_REPO = load_curated_vasp_directory()
        return _CURATED_REPO

    def repository_for(self, data_source: str) -> VASPRepository:
        """Select the correct reference: live -> curated public directory,
        otherwise -> synthetic seed (demo/tests). Synthetic data must never be
        used to attribute a live investigation."""
        if data_source == "live":
            return self.curated_repository
        return self._repo

    def lookup_address(
        self,
        address: str,
        chain: str,
        *,
        data_source: str = "demo",
    ) -> AddressIntelligence:
        repo = self.repository_for(data_source)
        matches = repo.lookup_by_address(address, chain)
        if not matches:
            return AddressIntelligence(
                address=address,
                chain=chain,
                is_known_vasp=False,
                confidence=0.0,
            )

        best = max(matches, key=lambda m: m.confidence)
        entity = repo.get_entity(best.vasp_name)

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