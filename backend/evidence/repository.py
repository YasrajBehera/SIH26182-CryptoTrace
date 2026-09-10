from typing import Dict, List, Optional

from evidence.models import EvidenceRecord


class EvidenceRepository:
    def __init__(self) -> None:
        self._records: Dict[str, EvidenceRecord] = {}
        self._by_attribution: Dict[str, List[str]] = {}
        self._by_address: Dict[str, List[str]] = {}

    def store(self, record: EvidenceRecord) -> None:
        self._records[record.evidence_id] = record
        self._by_attribution.setdefault(record.attribution_id, []).append(
            record.evidence_id
        )
        addr_key = f"{record.address.lower()}:{record.chain}"
        self._by_address.setdefault(addr_key, []).append(record.evidence_id)

    def get(self, evidence_id: str) -> Optional[EvidenceRecord]:
        return self._records.get(evidence_id)

    def get_by_attribution(self, attribution_id: str) -> List[EvidenceRecord]:
        ids = self._by_attribution.get(attribution_id, [])
        return [self._records[eid] for eid in ids if eid in self._records]

    def get_by_address(self, address: str, chain: str) -> List[EvidenceRecord]:
        addr_key = f"{address.lower()}:{chain}"
        ids = self._by_address.get(addr_key, [])
        return [self._records[eid] for eid in ids if eid in self._records]

    def count(self) -> int:
        return len(self._records)
