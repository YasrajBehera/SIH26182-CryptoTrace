import pytest

from evidence.models import EvidenceRecord, EvidenceType, Provenance
from evidence.repository import EvidenceRepository
from evidence.service import EvidenceService


class TestEvidenceModels:
    def test_evidence_type_enum(self):
        assert EvidenceType.GRAPH_PROXIMITY.value == "graph_proximity"
        assert EvidenceType.KNOWN_ADDRESS_MATCH.value == "known_address_match"
        assert EvidenceType.TEMPORAL_CONSISTENCY.value == "temporal_consistency"
        assert EvidenceType.TRANSACTION_FLOW.value == "transaction_flow"
        assert EvidenceType.CLUSTER_EVIDENCE.value == "cluster_evidence"

    def test_provenance_creation(self):
        prov = Provenance(
            created_at="2025-01-01T00:00:00Z",
            created_by="attribution_engine",
            method="test",
        )
        assert prov.version == "0.1.0"
        assert prov.created_by == "attribution_engine"

    def test_evidence_record_creation(self):
        prov = Provenance(created_at="2025-01-01T00:00:00Z", method="test")
        record = EvidenceRecord(
            evidence_id="ev-test123",
            attribution_id="attr-abc",
            evidence_type=EvidenceType.GRAPH_PROXIMITY,
            address="0x123",
            chain="eth",
            confidence=0.85,
            description="test evidence",
            provenance=prov,
        )
        assert record.evidence_id == "ev-test123"
        assert record.confidence == 0.85


class TestEvidenceRepository:
    def test_store_and_retrieve(self):
        repo = EvidenceRepository()
        prov = Provenance(created_at="2025-01-01T00:00:00Z", method="test")
        record = EvidenceRecord(
            evidence_id="ev-1",
            attribution_id="attr-1",
            evidence_type=EvidenceType.GRAPH_PROXIMITY,
            address="0x123",
            chain="eth",
            confidence=0.5,
            provenance=prov,
        )
        repo.store(record)
        assert repo.get("ev-1") is record
        assert repo.get("ev-nonexistent") is None

    def test_get_by_attribution(self):
        repo = EvidenceRepository()
        prov = Provenance(created_at="2025-01-01T00:00:00Z", method="test")
        for i in range(3):
            repo.store(EvidenceRecord(
                evidence_id=f"ev-{i}",
                attribution_id="attr-1",
                evidence_type=EvidenceType.GRAPH_PROXIMITY,
                address="0x123",
                chain="eth",
                confidence=0.5,
                provenance=prov,
            ))
        repo.store(EvidenceRecord(
            evidence_id="ev-other",
            attribution_id="attr-2",
            evidence_type=EvidenceType.KNOWN_ADDRESS_MATCH,
            address="0x123",
            chain="eth",
            confidence=0.7,
            provenance=prov,
        ))
        results = repo.get_by_attribution("attr-1")
        assert len(results) == 3
        assert all(r.attribution_id == "attr-1" for r in results)

    def test_get_by_address(self):
        repo = EvidenceRepository()
        prov = Provenance(created_at="2025-01-01T00:00:00Z", method="test")
        repo.store(EvidenceRecord(
            evidence_id="ev-a",
            attribution_id="attr-1",
            evidence_type=EvidenceType.GRAPH_PROXIMITY,
            address="0x123",
            chain="eth",
            confidence=0.5,
            provenance=prov,
        ))
        results = repo.get_by_address("0x123", "eth")
        assert len(results) == 1
        assert repo.get_by_address("0x123", "bsc") == []
        assert repo.get_by_address("0x999", "eth") == []

    def test_count(self):
        repo = EvidenceRepository()
        assert repo.count() == 0
        prov = Provenance(created_at="2025-01-01T00:00:00Z", method="test")
        repo.store(EvidenceRecord(
            evidence_id="ev-1",
            attribution_id="attr-1",
            evidence_type=EvidenceType.GRAPH_PROXIMITY,
            address="0x1",
            chain="eth",
            confidence=0.5,
            provenance=prov,
        ))
        assert repo.count() == 1


class TestEvidenceService:
    def test_create_evidence(self):
        svc = EvidenceService()
        record = svc.create_evidence(
            attribution_id="attr-test",
            evidence_type=EvidenceType.GRAPH_PROXIMITY,
            address="0x123",
            chain="eth",
            confidence=0.8,
            description="test",
        )
        assert record.evidence_id.startswith("ev-")
        assert record.attribution_id == "attr-test"
        assert record.confidence == 0.8

    def test_create_evidence_clamps_confidence(self):
        svc = EvidenceService()
        record = svc.create_evidence(
            attribution_id="attr-1",
            evidence_type=EvidenceType.GRAPH_PROXIMITY,
            address="0x1",
            chain="eth",
            confidence=1.5,
        )
        assert record.confidence == 1.0

        record2 = svc.create_evidence(
            attribution_id="attr-1",
            evidence_type=EvidenceType.GRAPH_PROXIMITY,
            address="0x1",
            chain="eth",
            confidence=-0.5,
        )
        assert record2.confidence == 0.0

    def test_get_evidence(self):
        svc = EvidenceService()
        record = svc.create_evidence(
            attribution_id="attr-1",
            evidence_type=EvidenceType.KNOWN_ADDRESS_MATCH,
            address="0xabc",
            chain="eth",
            confidence=0.9,
        )
        found = svc.get_evidence(record.evidence_id)
        assert found is not None
        assert found.evidence_type == EvidenceType.KNOWN_ADDRESS_MATCH

    def test_get_evidence_not_found(self):
        svc = EvidenceService()
        assert svc.get_evidence("nonexistent") is None

    def test_get_evidence_for_attribution(self):
        svc = EvidenceService()
        svc.create_evidence(
            attribution_id="attr-1",
            evidence_type=EvidenceType.GRAPH_PROXIMITY,
            address="0x1",
            chain="eth",
            confidence=0.5,
        )
        svc.create_evidence(
            attribution_id="attr-1",
            evidence_type=EvidenceType.TEMPORAL_CONSISTENCY,
            address="0x1",
            chain="eth",
            confidence=0.6,
        )
        svc.create_evidence(
            attribution_id="attr-2",
            evidence_type=EvidenceType.TRANSACTION_FLOW,
            address="0x1",
            chain="eth",
            confidence=0.7,
        )
        results = svc.get_evidence_for_attribution("attr-1")
        assert len(results) == 2

    def test_get_evidence_for_address(self):
        svc = EvidenceService()
        svc.create_evidence(
            attribution_id="attr-1",
            evidence_type=EvidenceType.GRAPH_PROXIMITY,
            address="0x123",
            chain="eth",
            confidence=0.5,
        )
        svc.create_evidence(
            attribution_id="attr-2",
            evidence_type=EvidenceType.GRAPH_PROXIMITY,
            address="0x123",
            chain="eth",
            confidence=0.6,
        )
        results = svc.get_evidence_for_address("0x123", "eth")
        assert len(results) == 2

    def test_provenance_populated(self):
        svc = EvidenceService()
        record = svc.create_evidence(
            attribution_id="attr-1",
            evidence_type=EvidenceType.GRAPH_PROXIMITY,
            address="0x1",
            chain="eth",
            confidence=0.5,
            method="test_method",
        )
        assert record.provenance.created_by == "attribution_engine"
        assert record.provenance.method == "test_method"
        assert record.provenance.created_at is not None
