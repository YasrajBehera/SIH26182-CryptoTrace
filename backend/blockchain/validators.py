"""Ethereum address validation utilities.

Implements format validation plus full EIP-55 checksum verification using a
proper keccak-256 implementation (eth_hash) so the checksum check is real,
not a fake/misleading approximation.

Policy:
- All-lowercase and all-uppercase addresses are accepted without checksum
  verification (many tools produce these and they remain valid on the network).
- Mixed-case addresses must satisfy the EIP-55 checksum or they are rejected.
"""

from __future__ import annotations

import re

from eth_hash.auto import keccak

_ADDRESS_RE = re.compile(r"^(0[xX])[0-9a-fA-F]{40}$")


class InvalidAddressError(ValueError):
    """Raised when an address fails validation."""


def is_valid_address(address: str) -> bool:
    """Return True if the address is a valid Ethereum address."""
    address = (address or "").strip()
    if not _ADDRESS_RE.match(address):
        return False
    hex_part = address[2:]
    if hex_part in (hex_part.lower(), hex_part.upper()):
        return True
    return _verify_checksum(hex_part)


def validate_address(address: str) -> str:
    """Validate an address and return it in canonical lowercase form.

    Raises InvalidAddressError if invalid.
    """
    address = (address or "").strip()
    if not is_valid_address(address):
        raise InvalidAddressError("Invalid Ethereum address.")
    return address.lower()


def _verify_checksum(hex_part: str) -> bool:
    """Verify the EIP-55 mixed-case checksum of a 40-char hex string."""
    lower = hex_part.lower()
    digest = keccak(lower.encode("ascii")).hex()
    for i, char in enumerate(hex_part):
        if char.isdigit():
            continue
        nibble = int(digest[i], 16)
        should_be_upper = nibble >= 8
        if should_be_upper and not char.isupper():
            return False
        if not should_be_upper and char.isupper():
            return False
    return True
