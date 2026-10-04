"""Chain registry and resolver.

Two rules this module exists to enforce:

1. **A ``0x`` prefix does not mean Ethereum.** Every EVM-compatible network uses
   20-byte hex addresses, so ``0xabc...`` exists simultaneously on Ethereum,
   Ronin, BNB Chain, Polygon, ... Address format alone can therefore never
   decide which chain a wallet lives on. The chain is either supplied by the
   caller or resolved through an explicit, documented registry entry.

2. **Chain is part of wallet identity.** The canonical identity of a wallet is
   ``(chain, address)``, never the bare address. ``eth:0xabc...`` and
   ``ronin:0xabc...`` are different investigation contexts and must never be
   merged (see :func:`wallet_id` and ``graph.schema.address_key``).

Supported canonical chain ids are declared here; every other value raises
:class:`~blockchain.errors.UnsupportedChainError`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from blockchain.errors import InvalidAddressError, UnsupportedChainError

# EVM chains all share the 20-byte hex address shape. Used for *format*
# validation only - never for chain inference.
_EVM_ADDRESS_RE = re.compile(r"^0[xX][0-9a-fA-F]{40}$")

# Future chains that must not be silently coerced to Ethereum. Declared as
# recognised-but-unavailable so the API can answer "provider not configured"
# instead of "unknown chain", and so the frontend can list them as planned.
KNOWN_UNAVAILABLE_CHAINS = ("bsc", "polygon", "tron", "solana")


@dataclass(frozen=True)
class ChainSpec:
    """Static, provider-agnostic description of one supported chain."""

    #: Canonical lowercase chain id, e.g. ``"eth"``.
    id: str
    #: Human label used by the UI and reports.
    label: str
    #: EIP-155 chain id as reported by ``eth_chainId``. ``None`` for non-EVM
    #: chains. Stored as a string so it round-trips the RPC hex value verbatim.
    evm_chain_id: Optional[str] = None
    #: Address format understood by this chain.
    address_format: str = "evm"
    #: Native gas-token symbol used when a provider cannot resolve a token symbol.
    native_symbol: str = "ETH"
    #: Public explorer base URL, used for links and manual cross-checking.
    explorer: str = ""
    #: Whether a provider for this chain is implemented in this deployment.
    enabled: bool = True
    #: Short note surfaced when the chain is recognised but not enabled.
    note: str = ""


CHAIN_REGISTRY: Dict[str, ChainSpec] = {
    "eth": ChainSpec(
        id="eth",
        label="Ethereum",
        evm_chain_id="1",
        native_symbol="ETH",
        explorer="https://etherscan.io",
    ),
    "ronin": ChainSpec(
        id="ronin",
        label="Ronin",
        evm_chain_id="2020",
        native_symbol="RON",
        explorer="https://app.roninchain.com",
    ),
}

# Accepted spellings -> canonical chain id. Keys must stay lowercase.
CHAIN_ALIASES: Dict[str, str] = {
    "eth": "eth",
    "ethereum": "eth",
    "ethereum-mainnet": "eth",
    "mainnet": "eth",
    "ronin": "ronin",
    "ronin-mainnet": "ronin",
    "roninchain": "ronin",
    "ronin chain": "ronin",
    # Recognised but not yet implemented: kept here so callers get an honest
    # "provider not configured" answer instead of "unknown chain".
    "bsc": "bsc",
    "bnb": "bsc",
    "bnb-chain": "bsc",
    "bnb smart chain": "bsc",
    "polygon": "polygon",
    "matic": "polygon",
    "tron": "tron",
    "trc20": "tron",
    "solana": "solana",
    "sol": "solana",
}

# Chains that are recognised but have no provider in this deployment.
UNIMPLEMENTED_CHAINS: Dict[str, str] = {
    "bsc": "No BNB Chain provider is implemented yet.",
    "polygon": "No Polygon provider is implemented yet.",
    "tron": "No Tron provider is implemented yet (non-EVM address format).",
    "solana": "No Solana provider is implemented yet (non-EVM address format).",
}


def supported_chains() -> list[str]:
    """Canonical ids of every chain with an enabled provider, sorted."""
    return sorted(c for c, spec in CHAIN_REGISTRY.items() if spec.enabled)


def normalize_chain(chain: Optional[str]) -> str:
    """Normalize a user-supplied chain string to its canonical id.

    Raises ``ValueError`` for an empty/unknown value; use :func:`resolve_chain`
    to get the typed :class:`UnsupportedChainError` instead.
    """
    key = (chain or "").strip().lower()
    if not key:
        raise ValueError("chain is required")
    canonical = CHAIN_ALIASES.get(key)
    if canonical is None:
        raise ValueError(f"unknown chain '{chain}'")
    return canonical


def canonical_chain(chain: Optional[str]) -> str:
    """Best-effort canonical chain id that never raises.

    Reference data (the curated VASP directory, fixtures) may legitimately carry
    a chain id this deployment has no provider for (``bsc``, ``polygon``, ...).
    Those ids are still passed through :func:`normalize_chain` so ``"bnb"`` and
    ``"bnb-chain"`` index the same bucket, but an entirely unrecognised value is
    returned lowercased instead of raising, so storing and comparing a directory
    entry can never crash a lookup.
    """
    try:
        return normalize_chain(chain)
    except ValueError:
        return (chain or "").strip().lower()


def normalize_address(address: Optional[str]) -> str:
    """Canonical form of an address for identity comparison.

    Every EVM chain uses the same 20-byte hex shape and differing letter case
    never denotes a different account, so identity comparison is always
    ``(chain, normalized address)``. Format/chain validation is a separate
    concern (:func:`validate_address_for_chain`); this helper only makes two
    spellings of the same account compare equal and never raises, so it is safe
    to use while indexing and matching reference data.
    """
    return (address or "").strip().lower()


def resolve_chain(chain: Optional[str]) -> ChainSpec:
    """Resolve a chain string to its :class:`ChainSpec`.

    A missing chain is *never* inferred from the address format. Callers pass
    ``None`` only when the caller deliberately wants the deployment default,
    which must be requested explicitly (see ``DEFAULT_CHAIN``).
    """
    try:
        canonical = normalize_chain(chain)
    except ValueError as exc:
        raise UnsupportedChainError(
            str(chain or "<empty>"),
            supported=supported_chains(),
        ) from exc

    if canonical in UNIMPLEMENTED_CHAINS:
        raise UnsupportedChainError(
            canonical,
            supported=supported_chains(),
        )

    spec = CHAIN_REGISTRY.get(canonical)
    if spec is None or not spec.enabled:
        raise UnsupportedChainError(canonical, supported=supported_chains())
    return spec


def is_recognised_but_unavailable(chain: Optional[str]) -> bool:
    """True when the chain is a known future chain with no provider yet."""
    try:
        return normalize_chain(chain) in UNIMPLEMENTED_CHAINS
    except ValueError:
        return False


def unavailable_reason(chain: Optional[str]) -> str:
    """Human-readable reason a recognised chain cannot be investigated."""
    try:
        canonical = normalize_chain(chain)
    except ValueError:
        return f"Unknown chain '{chain}'."
    return UNIMPLEMENTED_CHAINS.get(
        canonical, f"Chain '{canonical}' has no configured provider."
    )


def validate_address_for_chain(address: str, chain: str) -> str:
    """Validate ``address`` for ``chain`` and return it lowercased.

    Format validation only. A valid EVM address is valid on every EVM chain, so
    this cannot and does not prove which chain the address belongs to - it only
    rejects input that could never be a wallet on the selected chain.
    """
    spec = resolve_chain(chain)
    candidate = (address or "").strip()
    if not candidate:
        raise InvalidAddressError("Wallet address is required.")
    if spec.address_format == "evm" and not _EVM_ADDRESS_RE.match(candidate):
        raise InvalidAddressError(
            f"'{candidate}' is not a valid {spec.label} address "
            "(expected a 0x-prefixed 20-byte hex address)."
        )
    return candidate.lower()


def wallet_id(chain: str, address: str) -> str:
    """Canonical ``(chain, address)`` wallet identity, e.g. ``ronin:0xabc...``."""
    return f"{canonical_chain(chain)}:{normalize_address(address)}"


def split_wallet_id(value: str) -> Tuple[str, str]:
    """Inverse of :func:`wallet_id`."""
    raw = (value or "").strip()
    chain, _, address = raw.partition(":")
    return chain, address


#: Chain used when a caller explicitly asks for the deployment default.
#: It is a deployment *configuration*, never an inference from the address.
DEFAULT_CHAIN = "eth"