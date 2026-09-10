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
    address: str
    chain: str
    vasp_name: str
    address_type: AddressType = AddressType.UNKNOWN
    source: str = "synthetic"
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    confidence: float = Field(0.0, ge=0.0, le=1.0)


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
    is_known_vasp: bool = False
    all_matches: list[VASPAddress] = Field(default_factory=list)
