"""Explicit, typed failure modes for the blockchain provider layer.

Every failure that can occur while obtaining chain data has its own exception so
callers (pipeline, API, UI) can distinguish them instead of collapsing them into
a generic error and, worse, into synthetic data.

The pipeline imports these directly from ``blockchain.errors`` so there is exactly
one definition of each failure mode in the project.
"""

from __future__ import annotations


class BlockchainError(RuntimeError):
    """Base class for every blockchain-provider failure."""

    #: Short machine-readable status surfaced to API clients / UI.
    status = "BLOCKCHAIN_ERROR"
    #: HTTP status FastAPI should answer with.
    http_status = 502


class UnsupportedChainError(BlockchainError):
    """The requested chain is not registered (or not enabled) in this deployment.

    Raised instead of guessing a chain from the address format: a ``0x`` prefix
    only proves the address is EVM-shaped, not which network it belongs to.
    """

    status = "UNSUPPORTED_CHAIN"
    http_status = 400

    def __init__(self, chain: str, supported: list[str] | None = None) -> None:
        self.chain = chain
        self.supported = sorted(supported or [])
        detail = (
            f"Chain '{chain}' is not supported by this deployment."
        )
        if self.supported:
            detail += f" Supported chains: {', '.join(self.supported)}."
        else:
            detail += " No blockchain provider is configured."
        super().__init__(detail)


class ProviderNotConfiguredError(BlockchainError):
    """The chain is supported but no credentials/endpoint are configured.

    Distinct from "configured but the provider failed": this is an operator
    action, not a transient fault.
    """

    status = "NOT_CONFIGURED"
    http_status = 503

    def __init__(self, chain: str, message: str = "") -> None:
        self.chain = chain
        super().__init__(
            message
            or f"Blockchain provider for chain '{chain}' is not configured."
        )


class InvalidAddressError(BlockchainError):
    """The supplied address is not valid for the resolved chain."""

    status = "INVALID_ADDRESS"
    http_status = 400

    def __init__(self, message: str = "Invalid address for the selected chain.") -> None:
        super().__init__(message)


class LiveDataUnavailableError(BlockchainError):
    """Live chain data was requested but could not be obtained.

    This is the single most important rule in the project: raising this error
    must never be converted into synthetic/demo data. A live request either
    returns real data or an honest failure.
    """

    status = "LIVE_DATA_UNAVAILABLE"
    http_status = 503

    def __init__(self, message: str = "Live blockchain data is unavailable.", *, chain: str = "") -> None:
        self.chain = chain
        super().__init__(message)


class ProviderRateLimitError(LiveDataUnavailableError):
    """The upstream provider rejected the request for rate-limit reasons."""

    status = "PROVIDER_RATE_LIMITED"
    http_status = 429


class ProviderTimeoutError(LiveDataUnavailableError):
    """The upstream provider did not answer within the configured timeout."""

    status = "PROVIDER_TIMEOUT"
    http_status = 504


class ProviderResponseError(LiveDataUnavailableError):
    """The provider answered, but with an error or a malformed payload.

    A malformed body is surfaced as a provider error rather than being silently
    coerced into an empty (but successful-looking) result set.
    """

    status = "PROVIDER_ERROR"
    http_status = 502