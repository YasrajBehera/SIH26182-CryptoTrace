from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AddressType(str, Enum):
    HOT_WALLET = "hot_wallet"
    COLD_WALLET = "cold_wallet"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRADING = "trading"
    CUSTODIAL = "custodial"
    UNKNOWN = "unknown"


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    DISPUTED = "disputed"


class VASPEntity(BaseModel):
    name: str
    entity_type: str = Field(
        ...,
        description="exchange, defi, mixer, protocol, merchant, other",
    )
    jurisdiction: str = "unknown"


class VASPAddress(BaseModel):
    """One VASP-controlled address, always scoped to exactly one chain.

    ``chain`` is part of the identity, not metadata: the same 20-byte hex string
    can belong to unrelated accounts on different EVM chains, so an entry is
    only ever matched as ``(chain, address)``. Provenance fields
    (:attr:`source_url`, :attr:`evidence`, :attr:`verification_tx_hash`) record
    the public artefact the label was checked against so a match can be traced
    back to a real, checkable source instead of asserted.
    """

    address: str
    chain: str
    vasp_name: str
    address_type: AddressType = AddressType.UNKNOWN
    source: str = "synthetic"
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    #: Public, human-checkable URL the label/address was verified against.
    source_url: Optional[str] = None
    #: Why this entry is considered verified, in plain words.
    evidence: Optional[str] = None
    #: A real on-chain transaction hash that demonstrates the entry's address is
    #: an active, explorer-labelled account. This attests the LABEL only - it is
    #: never evidence that any investigated wallet transacted with this address.
    verification_tx_hash: Optional[str] = None
    #: Block of :attr:`verification_tx_hash`, when known.
    verification_block: Optional[int] = None


class AddressIntelligence(BaseModel):
    address: str
    chain: str
    known_vasp: Optional[str] = None
    address_type: Optional[str] = None
    entity_type: Optional[str] = None
    jurisdiction: Optional[str] = None
    verification_status: Optional[str] = None
    confidence: float = 0.0
    source: Optional[str] = None
    #: Public URL the matched label was verified against, when recorded.
    source_url: Optional[str] = None
    #: The VASP-controlled address that actually matched, on ``chain``.
    #: ``address`` is the queried wallet; this is the counterparty label hit.
    matched_address: Optional[str] = None
    is_known_vasp: bool = False
    all_matches: list[VASPAddress] = Field(default_factory=list)
