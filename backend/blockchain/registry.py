"""Chain -> provider registry.

The single place where a chain id becomes a provider instance. Everything
downstream (pipeline, API, UI) asks for a chain and receives a
:class:`~blockchain.providers.BlockchainProvider`; it never learns which vendor
served the data.
"""

from __future__ import annotations

from typing import Callable, Dict

from blockchain.chains import resolve_chain, supported_chains
from blockchain.errors import UnsupportedChainError
from blockchain.providers import BlockchainProvider

ProviderFactory = Callable[[], BlockchainProvider]


def _make_ethereum() -> BlockchainProvider:
    from blockchain.ethereum_provider import EthereumProvider

    return EthereumProvider()


def _make_ronin() -> BlockchainProvider:
    from blockchain.ronin_provider import RoninProvider

    return RoninProvider()


#: Canonical chain id -> zero-argument provider factory. Adding a chain means
#: adding one entry here plus a ChainSpec; no pipeline, graph, attribution or
#: evidence code changes.
PROVIDER_FACTORIES: Dict[str, ProviderFactory] = {
    "eth": _make_ethereum,
    "ronin": _make_ronin,
}


def provider_factory(chain: str) -> ProviderFactory:
    """Return the factory for ``chain`` or raise ``UnsupportedChainError``."""
    spec = resolve_chain(chain)
    factory = PROVIDER_FACTORIES.get(spec.id)
    if factory is None:
        raise UnsupportedChainError(spec.id, supported=supported_chains())
    return factory


def get_provider(chain: str, **kwargs) -> BlockchainProvider:
    """Build the provider for ``chain``.

    Construction never performs I/O, so a missing credential surfaces as an
    explicit ``ProviderNotConfiguredError``/``NOT_CONFIGURED`` status at fetch
    time rather than as an empty result set.
    """
    factory = provider_factory(chain)
    provider = factory()
    for name, value in kwargs.items():
        if value is not None:
            setattr(provider, name, value)
    return provider


def registered_chains() -> list[str]:
    """Chain ids that currently have a provider factory."""
    return sorted(PROVIDER_FACTORIES)


def provider_status() -> Dict[str, Dict[str, object]]:
    """Operator-facing configuration snapshot used by the status surfaces."""
    status: Dict[str, Dict[str, object]] = {}
    for chain in registered_chains():
        try:
            provider = get_provider(chain)
        except UnsupportedChainError:
            status[chain] = {"status": "UNSUPPORTED_CHAIN"}
            continue
        transports: list[str] = []
        configured = False
        if hasattr(provider, "describe_transports"):
            transports = list(provider.describe_transports())
            configured = bool(transports)
        elif hasattr(provider, "is_configured"):
            configured = bool(provider.is_configured())
        status[chain] = {
            "status": "CONFIGURED" if configured else "NOT_CONFIGURED",
            "provider": getattr(provider, "provider_name", ""),
            "transports": transports,
        }
    return status