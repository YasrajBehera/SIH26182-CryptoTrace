import uuid
from datetime import datetime, timezone
from typing import List

from evidence.models import EvidenceRecord, EvidenceType, Provenance
from evidence.repository import EvidenceRepository


class EvidenceService:
    def __init__(self, repository: EvidenceRepository | None = None) -> None:
        self._repo = repository or EvidenceRepository()

    @property
    def repository(self) -> EvidenceRepository:
        return self._repo

    def create_evidence(
        self,
        attribution_id: str,
        evidence_type: EvidenceType,
        address: str,
        chain: str,
        confidence: float,
        description: str = "",
        tx_hash: str | None = None,
        graph_path: List[str] | None = None,
        source: str = "synthetic",
        timestamp: int | None = None,
        method: str = "attribution_engine_v1",
    ) -> EvidenceRecord:
        record = EvidenceRecord(
            evidence_id=f"ev-{uuid.uuid4().hex[:12]}",
            attribution_id=attribution_id,
            evidence_type=evidence_type,
            address=address.lower(),
            chain=chain,
            tx_hash=tx_hash,
            graph_path=graph_path,
            source=source,
            timestamp=timestamp,
            confidence=min(max(confidence, 0.0), 1.0),
            description=description,
            provenance=Provenance(
                created_at=datetime.now(timezone.utc).isoformat(),
                created_by="attribution_engine",
                method=method,
                version="0.1.0",
            ),
        )
        self._repo.store(record)
        return record

    def get_evidence(self, evidence_id: str) -> EvidenceRecord | None:
        return self._repo.get(evidence_id)

    def get_evidence_for_attribution(
        self, attribution_id: str
    ) -> List[EvidenceRecord]:
        return self._repo.get_by_attribution(attribution_id)

    def get_evidence_for_address(
        self, address: str, chain: str
    ) -> List[EvidenceRecord]:
        return self._repo.get_by_address(address, chain)
