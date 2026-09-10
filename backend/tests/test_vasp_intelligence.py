import pytest

from intelligence.models import AddressIntelligence, AddressType, VerificationStatus, VASPEntity, VASPAddress
from intelligence.repository import VASPRepository
from intelligence.service import VASPIntelligenceService
from intelligence.synthetic_data import seed_synthetic_vasp_data


class TestVASPModels:
    def test_address_type_enum(self):
        assert AddressType.HOT_WALLET.value == "hot_wallet"
        assert AddressType.COLD_WALLET.value == "cold_wallet"
        assert AddressType.UNKNOWN.value == "unknown"

    def test_verification_status_enum(self):
        assert VerificationStatus.VERIFIED.value == "verified"
        assert VerificationStatus.UNVERIFIED.value == "unverified"

    def test_vasp_entity_creation(self):
        entity = VASPEntity(name="TestExchange", entity_type="exchange", jurisdiction="US")
        assert entity.name == "TestExchange"
        assert entity.entity_type == "exchange"

    def test_vasp_address_creation(self):
        addr = VASPAddress(
            address="0xabc123",
            chain="eth",
            vasp_name="TestExchange",
            address_type=AddressType.HOT_WALLET,
            confidence=0.9,
        )
        assert addr.address == "0xabc123"
        assert addr.confidence == 0.9

    def test_vasp_address_defaults(self):
        addr = VASPAddress(address="0x1", chain="eth", vasp_name="X")
        assert addr.address_type == AddressType.UNKNOWN
        assert addr.verification_status == VerificationStatus.UNVERIFIED
        assert addr.confidence == 0.0


class TestVASPRepository:
    def test_add_and_lookup(self):
        repo = VASPRepository()
        addr = VASPAddress(
            address="0xtest",
            chain="eth",
            vasp_name="ExchangeX",
            verification_status=VerificationStatus.VERIFIED,
        )
        repo.add_address(addr)
        results = repo.lookup_by_address("0xtest", "eth")
        assert len(results) == 1
        assert results[0].vasp_name == "ExchangeX"

    def test_case_insensitive_lookup(self):
        repo = VASPRepository()
        addr = VASPAddress(
            address="0xABCD",
            chain="eth",
            vasp_name="ExchangeX",
        )
        repo.add_address(addr)
        results = repo.lookup_by_address("0xabcd", "eth")
        assert len(results) == 1

    def test_lookup_wrong_chain(self):
        repo = VASPRepository()
        addr = VASPAddress(address="0x1", chain="eth", vasp_name="X")
        repo.add_address(addr)
        results = repo.lookup_by_address("0x1", "bsc")
        assert len(results) == 0

    def test_get_known_vasps(self):
        repo = VASPRepository()
        repo.add_address(VASPAddress(
            address="0x1", chain="eth", vasp_name="A",
            verification_status=VerificationStatus.VERIFIED,
        ))
        repo.add_address(VASPAddress(
            address="0x2", chain="eth", vasp_name="B",
            verification_status=VerificationStatus.UNVERIFIED,
        ))
        known = repo.get_known_vasp_addresses("eth")
        assert len(known) == 1
        assert known[0].vasp_name == "A"

    def test_get_vasp_names_for_chain(self):
        repo = VASPRepository()
        repo.add_address(VASPAddress(address="0x1", chain="eth", vasp_name="A"))
        repo.add_address(VASPAddress(address="0x2", chain="eth", vasp_name="B"))
        repo.add_address(VASPAddress(address="0x3", chain="bsc", vasp_name="C"))
        names = repo.get_vasp_names_for_chain("eth")
        assert sorted(names) == ["A", "B"]

    def test_entity_management(self):
        repo = VASPRepository()
        entity = VASPEntity(name="Test", entity_type="exchange")
        repo.add_entity(entity)
        assert repo.get_entity("Test") == entity
        assert repo.get_entity("Nonexistent") is None


class TestSyntheticData:
    def test_seed_creates_data(self):
        repo = seed_synthetic_vasp_data()
        assert len(repo.get_all_entities()) == 5
        assert len(repo.get_all_addresses()) == 10

    def test_known_vasps_available(self):
        repo = seed_synthetic_vasp_data()
        known = repo.get_known_vasp_addresses("eth")
        assert len(known) >= 4

    def test_vasp_names(self):
        repo = seed_synthetic_vasp_data()
        names = repo.get_vasp_names_for_chain("eth")
        assert "SynthExchange_A" in names
        assert "SynthExchange_B" in names


class TestVASPIntelligenceService:
    def test_lookup_known_address(self):
        svc = VASPIntelligenceService()
        result = svc.lookup_address(
            "0xaabb000000000000000000000000000000000001", "eth"
        )
        assert result.is_known_vasp is True
        assert result.known_vasp == "SynthExchange_A"
        assert result.confidence == 0.95
        assert result.entity_type == "exchange"

    def test_lookup_unknown_address(self):
        svc = VASPIntelligenceService()
        result = svc.lookup_address("0xunknown00000000000000000000000000000000", "eth")
        assert result.is_known_vasp is False
        assert result.known_vasp is None
        assert result.confidence == 0.0

    def test_lookup_disputed_address(self):
        svc = VASPIntelligenceService()
        result = svc.lookup_address(
            "0xdead00000000000000000000000000000000000d", "eth"
        )
        assert result.is_known_vasp is False
        assert result.verification_status == "disputed"
        assert len(result.all_matches) == 1

    def test_lookup_multi_chain(self):
        svc = VASPIntelligenceService()
        eth_result = svc.lookup_address(
            "0xaabb000000000000000000000000000000000001", "eth"
        )
        bsc_result = svc.lookup_address(
            "0xaabb000000000000000000000000000000000001", "bsc"
        )
        assert eth_result.known_vasp == "SynthExchange_A"
        assert bsc_result.known_vasp == "SynthExchange_A"
        assert eth_result.confidence != bsc_result.confidence

    def test_address_intelligence_model(self):
        svc = VASPIntelligenceService()
        result = svc.lookup_address("0xunknown", "eth")
        assert isinstance(result, AddressIntelligence)
        assert result.address == "0xunknown"
