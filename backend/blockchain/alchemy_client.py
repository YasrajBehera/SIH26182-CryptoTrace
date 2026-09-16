"""Async Alchemy client for Ethereum asset transfers.

Wraps Alchemy's ``alchemy_getAssetTransfers`` JSON-RPC method, handling
timeouts, HTTP errors, API-level errors, validation and pagination.

Security notes:
- The API key is read from the environment, never hardcoded.
- The API key is never included in logs or exception messages.
- Pagination is capped so we never download unlimited chain history.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from blockchain.pagination import PaginationConfig

CHAIN_ID = "eth"
NETWORK = "eth-mainnet"


class AlchemyConfigError(RuntimeError):
    """Raised when the Alchemy API key is missing / misconfigured."""


class AlchemyAPIError(RuntimeError):
    """Raised when the Alchemy provider returns an API-level error."""


class AlchemyHTTPError(RuntimeError):
    """Raised when the Alchemy provider returns a non-2xx HTTP status."""


class AlchemyClient:
    """Minimal async client specialized for Alchemy asset transfers."""

    DEFAULT_CATEGORIES = ["external", "internal", "erc20"]

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        pagination: Optional[PaginationConfig] = None,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("ALCHEMY_API_KEY", "")
        key = (key or "").strip()
        if not key:
            raise AlchemyConfigError(
                "ALCHEMY_API_KEY is not set. Add it to backend/.env to enable live blockchain queries."
            )
        self._api_key = key
        self._base_url = base_url or f"https://{NETWORK}.g.alchemy.com/v2/{key}"
        self._timeout = timeout
        self._pagination = pagination or PaginationConfig()
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "AlchemyClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def get_transfers(
        self,
        wallet_address: str,
        direction: str,
        categories: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Fetch all transfers for a wallet in the given direction.

        ``direction`` must be ``"from"`` (outgoing) or ``"to"`` (incoming).
        Paginates until the pageKey runs out or a configured cap is reached.
        """
        cat = categories or self.DEFAULT_CATEGORIES
        page_key: Optional[str] = None
        collected: list[dict[str, Any]] = []
        pages = 0

        while pages < self._pagination.max_pages:
            params: dict[str, Any] = {
                "fromBlock": "0x0",
                "toBlock": "latest",
                "category": cat,
                "order": "asc",
                "withMetadata": True,
                "excludeZeroValue": False,
                "maxCount": "0x3e8",
            }
            if direction == "from":
                params["fromAddress"] = wallet_address
            else:
                params["toAddress"] = wallet_address
            if page_key:
                params["pageKey"] = page_key

            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "alchemy_getAssetTransfers",
                "params": [params],
            }

            result = await self._rpc(payload)
            transfers = result.get("transfers") or []
            collected.extend(transfers)

            remaining = self._pagination.max_transfers - len(collected)
            if remaining <= 0:
                # Stop early once we have reached the overall transfer cap.
                return collected[: self._pagination.max_transfers]

            page_key = result.get("pageKey")
            pages += 1
            if not page_key:
                break

        return collected[: self._pagination.max_transfers]

    async def get_block_timestamps(
        self, block_numbers: list[int]
    ) -> dict[int, Any]:
        """Resolve authoritative block timestamps from the chain.

        ``eth_getBlockByNumber`` returns the exact timestamp the chain recorded
        for each block, so ``block_number`` and ``block_timestamp`` in a
        normalized transfer always share one source of truth. Unresolvable
        blocks are omitted (the caller keeps whatever timestamp it has).
        """
        resolved: dict[int, Any] = {}
        for block_number in block_numbers:
            try:
                ts = await self.get_block_timestamp(block_number)
            except (AlchemyAPIError, AlchemyHTTPError):
                ts = None
            if ts is not None:
                resolved[block_number] = ts
        return resolved

    async def get_block_timestamp(self, block_number: int) -> Optional[int]:
        """Return the unix timestamp for a block, or None if unresolvable."""
        from datetime import datetime, timezone

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_getBlockByNumber",
            "params": [hex(block_number), False],
        }
        result = await self._rpc(payload)
        if not isinstance(result, dict):
            return None
        ts_hex = result.get("timestamp")
        if not ts_hex:
            return None
        try:
            ts = int(str(ts_hex), 16)
        except (TypeError, ValueError):
            return None
        if ts < 0:
            return None
        return int(datetime.fromtimestamp(ts, tz=timezone.utc).timestamp())

    async def is_healthy(self) -> bool:
        """Cheap live provider probe: fetch the latest block number.

        ``eth_blockNumber`` costs one lightweight JSON-RPC round trip and fails
        fast on a missing/expired key, wrong network, or unreachable endpoint —
        unlike a presence check that only inspects the environment. The result
        is discarded; we only prove the provider answered.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_blockNumber",
            "params": [],
        }
        client = self._get_client()
        try:
            response = await client.post(self._base_url, json=payload)
        except (httpx.TimeoutException, httpx.HTTPError):
            return False

        if response.status_code != 200:
            return False

        try:
            data = response.json()
        except ValueError:
            return False

        if not isinstance(data, dict) or "error" in data:
            return False

        block_hex = data.get("result")
        if not block_hex:
            return False
        try:
            return int(str(block_hex), 16) > 0
        except (TypeError, ValueError):
            return False

    async def _rpc(self, payload: dict[str, Any]) -> dict[str, Any]:
        client = self._get_client()
        try:
            response = await client.post(self._base_url, json=payload)
        except httpx.TimeoutException as exc:
            raise AlchemyAPIError("Blockchain provider timed out.") from exc
        except httpx.HTTPError as exc:
            raise AlchemyHTTPError("Blockchain provider unavailable (network error).") from exc

        if response.status_code != 200:
            raise AlchemyHTTPError(
                f"Blockchain provider returned HTTP {response.status_code}."
            )

        try:
            data = response.json()
        except ValueError:
            # A non-JSON body (e.g. an HTML error page from a misconfigured or
            # expired key) must surface as a provider error, not a crash.
            raise AlchemyAPIError(
                "Blockchain provider returned a non-JSON response."
            )
        if "error" in data:
            message = data["error"].get("message") or "unknown provider error"
            raise AlchemyAPIError(f"Blockchain provider error: {message}")

        result = data.get("result")
        if result is None:
            raise AlchemyAPIError("Blockchain provider returned no result.")
        if not isinstance(result, dict):
            raise AlchemyAPIError("Blockchain provider returned an unexpected result shape.")

        return result
