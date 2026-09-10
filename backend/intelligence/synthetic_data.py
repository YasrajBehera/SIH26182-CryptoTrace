from intelligence.models import AddressType, VerificationStatus, VASPEntity, VASPAddress
from intelligence.repository import VASPRepository


def seed_synthetic_vasp_data() -> VASPRepository:
    repo = VASPRepository()

    entities = [
        VASPEntity(name="SynthExchange_A", entity_type="exchange", jurisdiction="SG"),
        VASPEntity(name="SynthExchange_B", entity_type="exchange", jurisdiction="US"),
        VASPEntity(name="SynthDeFi_Protocol", entity_type="defi", jurisdiction="decentralized"),
        VASPEntity(name="SynthMixer_Service", entity_type="mixer", jurisdiction="unknown"),
        VASPEntity(name="SynthMerchant_X", entity_type="merchant", jurisdiction="IN"),
    ]
    for e in entities:
        repo.add_entity(e)

    addresses = [
        VASPAddress(
            address="0xaabb000000000000000000000000000000000001",
            chain="eth",
            vasp_name="SynthExchange_A",
            address_type=AddressType.HOT_WALLET,
            source="synthetic",
            verification_status=VerificationStatus.VERIFIED,
            confidence=0.95,
        ),
        VASPAddress(
            address="0xaabb000000000000000000000000000000000002",
            chain="eth",
            vasp_name="SynthExchange_A",
            address_type=AddressType.COLD_WALLET,
            source="synthetic",
            verification_status=VerificationStatus.VERIFIED,
            confidence=0.90,
        ),
        VASPAddress(
            address="0xccdd000000000000000000000000000000000003",
            chain="eth",
            vasp_name="SynthExchange_B",
            address_type=AddressType.HOT_WALLET,
            source="synthetic",
            verification_status=VerificationStatus.VERIFIED,
            confidence=0.92,
        ),
        VASPAddress(
            address="0xccdd000000000000000000000000000000000004",
            chain="eth",
            vasp_name="SynthExchange_B",
            address_type=AddressType.DEPOSIT,
            source="synthetic",
            verification_status=VerificationStatus.VERIFIED,
            confidence=0.88,
        ),
        VASPAddress(
            address="0xefff000000000000000000000000000000000005",
            chain="eth",
            vasp_name="SynthDeFi_Protocol",
            address_type=AddressType.TRADING,
            source="synthetic",
            verification_status=VerificationStatus.VERIFIED,
            confidence=0.85,
        ),
        VASPAddress(
            address="0x1122000000000000000000000000000000000006",
            chain="eth",
            vasp_name="SynthMixer_Service",
            address_type=AddressType.UNKNOWN,
            source="synthetic",
            verification_status=VerificationStatus.UNVERIFIED,
            confidence=0.40,
        ),
        VASPAddress(
            address="0x3344000000000000000000000000000000000007",
            chain="eth",
            vasp_name="SynthMerchant_X",
            address_type=AddressType.CUSTODIAL,
            source="synthetic",
            verification_status=VerificationStatus.VERIFIED,
            confidence=0.80,
        ),
        VASPAddress(
            address="0xaabb000000000000000000000000000000000001",
            chain="bsc",
            vasp_name="SynthExchange_A",
            address_type=AddressType.HOT_WALLET,
            source="synthetic",
            verification_status=VerificationStatus.VERIFIED,
            confidence=0.93,
        ),
        VASPAddress(
            address="0xccdd000000000000000000000000000000000003",
            chain="bsc",
            vasp_name="SynthExchange_B",
            address_type=AddressType.HOT_WALLET,
            source="synthetic",
            verification_status=VerificationStatus.VERIFIED,
            confidence=0.91,
        ),
        VASPAddress(
            address="0xdead00000000000000000000000000000000000d",
            chain="eth",
            vasp_name="SynthMixer_Service",
            address_type=AddressType.UNKNOWN,
            source="synthetic",
            verification_status=VerificationStatus.DISPUTED,
            confidence=0.25,
        ),
    ]
    for a in addresses:
        repo.add_address(a)

    return repo
