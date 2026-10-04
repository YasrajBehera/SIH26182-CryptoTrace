"""Ethereum provider.

This is an *adapter*, not a rewrite. All Alchemy-specific work (RPC calls,
pagination, block-timestamp backfill, normalization, de-duplication, wallet-store
persistence) already lives in :class:`blockchain.service.BlockchainService` and
:class:`blockchain.alchemy_client.AlchemyClient`; this class only selects them and
converts their result into a :class:`~blockchain.providers.ProviderResult`.

``AlchemyClient`` stays Ethereum-only by design. Adding a chain must never mean
teaching Alchemy's client about every network.
"""

from __future__ import annotations

import os
from typing import Optional

from blockchain.alchemy_client import (
    AlchemyAPIError,
    AlchemyClient,
    AlchemyConfigError,
    AlchemyHTTPError,
)
from blockchain.chains import resolve_chain, validate_address_for_chain
from blockchain.errors import (
    InvalidAddressError,
    LiveDataUnavailableError,
    ProviderNotConfiguredError,
    ProviderResponseError,
)
from blockchain.providers import (
    SOURCE_LIVE,
    STATUS_LIVE,
    STATUS_NO_DATA,
    BlockchainProvider,
    ProviderResult,
)
from blockchain.service import BlockchainService
from blockchain.validators import InvalidAddressError as AddressFormatError


def _map_alchemy_error(exc: Exception, chain: str) -> Exception:
    """Translate Alchemy-specific failures into the shared error vocabulary."""
    if isinstance(exc, AlchemyConfigError):
        return ProviderNotConfiguredError(chain, str(exc))
    if isinstance(exc, AlchemyAPIError):
        message = str(exc)
        if "rate limit" in message.lower() or "429" in message:
            from blockchain.errors import ProviderRateLimitError

            return ProviderRateLimitError(message, chain=chain)
        return ProviderResponseError(message, chain=chain)
    if isinstance(exc, AlchemyHTTPError):
        return ProviderResponseError(str(exc), chain=chain)
    if isinstance(exc, AddressFormatError):
        return InvalidAddressError(str(exc))
    return exc


class EthereumProvider(BlockchainProvider):
    """Live Ethereum transfers via the project's existing Alchemy integration."""

    chain_name = "eth"
    provider_name = "alchemy"

    def __init__(
        self,
        client: Optional[AlchemyClient] = None,
        *,
        service: Optional[BlockchainService] = None,
        wallet_repository=None,
    ) -> None:
        self._client = client
        self._service = service
        self._wallet_repository = wallet_repository

    # -- construction helpers ------------------------------------------------

    @staticmethod
    def build(
        api_key: Optional[str] = None,
        *,
        wallet_repository=None,
    ) -> "EthereumProvider":
        """Construct from configuration, raising if the key is absent."""
        key = (api_key if api_key is not None else os.environ.get("ALCHEMY_API_KEY", "")).strip()
        if not key:
            raise ProviderNotConfiguredError(
                "eth",
                "ALCHEMY_API_KEY is not set. Add it to backend/.env to enable "
                "live Ethereum investigations.",
            )
        return EthereumProvider(
            AlchemyClient(api_key=key),
            wallet_repository=wallet_repository,
        )

    def is_configured(self) -> bool:
        if self._client is not None or self._service is not None:
            return True
        return bool(os.environ.get("ALCHEMY_API_KEY", "").strip())

    def describe_transports(self) -> list[str]:
        """Transports that could actually serve this chain right now."""
        return ["alchemy"] if self.is_configured() else []

    # -- provider contract ---------------------------------------------------

    async def get_transfers(
        self,
        address: str,
        limit: Optional[int] = None,
    ) -> ProviderResult:
        chain = resolve_chain(self.chain_name)
        normalized_address = validate_address_for_chain(address, chain.id)

        if self._service is None:
            if self._client is None:
                key = os.environ.get("ALCHEMY_API_KEY", "").strip()
                if not key:
                    raise ProviderNotConfiguredError(
                        self.chain_name,
                        "ALCHEMY_API_KEY is not set. Live Ethereum data is "
                        "unavailable; no synthetic data is substituted.",
                    )
                self._client = AlchemyClient(api_key=key)
            self._service = BlockchainService(
                client=self._client,
                wallet_repository=self._wallet_repository,
            )

        try:
            response = await self._service.get_wallet_transfers(
                normalized_address,
                chain=self.chain_name,
                limit=limit,
            )
        except ProviderNotConfiguredError:
            raise
        except LiveDataUnavailableError:
            raise
        except (AlchemyConfigError, AlchemyAPIError, AlchemyHTTPError) as exc:
            raise _map_alchemy_error(exc, self.chain_name) from exc
        except AddressFormatError as exc:
            raise InvalidAddressError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - provider faults must be explicit
            raise LiveDataUnavailableError(
                f"Ethereum provider request failed: {type(exc).__name__}.",
                chain=self.chain_name,
            ) from exc

        pagination = response.pagination
        limitations: list[str] = []
        if pagination.truncated:
            limitations.append(
                f"History truncated at {pagination.max_transfers} transfers; "
                "the wallet has more on-chain activity than was fetched."
            )
        if pagination.source == "database":
            limitations.append(
                "Served from the persisted wallet store (previously fetched "
                "from the provider), not a fresh provider round trip."
            )
        if pagination.skipped:
            limitations.append(
                f"{pagination.skipped} malformed provider record(s) were skipped."
            )

        status = STATUS_LIVE
        if not response.transfers:
            # A real answer from the provider that simply found nothing. This is
            # NOT an error and NOT synthetic data.
            status = STATUS_NO_DATA
            limitations.append(
                "Provider returned no transfers for this address on Ethereum."
            )

        return ProviderResult(
            chain=self.chain_name,
            address=normalized_address,
            data_source=SOURCE_LIVE,
            status=status,
            provider=self.provider_name,
            transfers=list(response.transfers),
            truncated=bool(pagination.truncated),
            limitations=limitations,
        )

    async def is_healthy(self) -> bool:
        if self._client is None and not os.environ.get("ALCHEMY_API_KEY", "").strip():
            return False
        try:
            if self._service is None:
                provider = self.build(wallet_repository=self._wallet_repository)
                self._client = provider._client
                self._service = provider._service
            return await self._service.provider_health()
        except Exception:  # noqa: BLE001 - health probes must never raise
            return False

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            self._service = None