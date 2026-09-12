"""Blockchain service layer.

The rest of the application talks to this service instead of calling Alchemy
directly. It validates the address, fetches incoming and outgoing transfers,
combines and de-duplicates them, normalizes each transfer and returns a
``WalletTransfers`` response model sorted chronologically.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from blockchain.alchemy_client import AlchemyClient
from blockchain.models import BlockchainTransfer, PaginationInfo, WalletTransfers
from blockchain.pagination import PaginationConfig
from blockchain.validators import InvalidAddressError, validate_address

CHAIN_ID = "eth"


class BlockchainService:
    """High-level service for querying a wallet's transfer history."""

    def __init__(
        self,
        client: Optional[AlchemyClient] = None,
        pagination: Optional[PaginationConfig] = None,
    ) -> None:
        self._client = client
        self._pagination = pagination or PaginationConfig()

    async def get_wallet_transfers(
        self,
        wallet_address: str,
        chain: str = CHAIN_ID,
        limit: Optional[int] = None,
    ) -> WalletTransfers:
        """Return a normalized, de-duplicated, chronologically sorted transfer set."""
        try:
            normalized_address = validate_address(wallet_address)
        except InvalidAddressError as exc:
            raise InvalidAddressError(str(exc)) from exc

        config = self._apply_overrides(limit)

        async with self._client or AlchemyClient(pagination=config) as client:
            outgoing_raw = await client.get_transfers(normalized_address, direction="from")
            incoming_raw = await client.get_transfers(normalized_address, direction="to")

        transfers: list[BlockchainTransfer] = []
        skipped = 0
        for direction, raw_rows in (("in", incoming_raw), ("out", outgoing_raw)):
            normalized, malformed = self._normalize_many(raw_rows, direction)
            transfers.extend(normalized)
            skipped += malformed

        transfers = self._deduplicate(transfers)
        transfers.sort(key=self._sort_key)

        max_transfers = config.max_transfers
        truncated = len(transfers) > max_transfers
        if truncated:
            transfers = transfers[:max_transfers]

        return WalletTransfers(
            wallet_address=normalized_address,
            chain=chain,
            transfers=transfers,
            pagination=PaginationInfo(
                max_transfers=max_transfers,
                fetched=len(transfers),
                truncated=truncated,
                skipped=skipped,
            ),
        )

    def _apply_overrides(self, limit: Optional[int]) -> PaginationConfig:
        config = PaginationConfig(
            max_pages=self._pagination.max_pages,
            max_transfers=self._pagination.max_transfers,
        )
        if limit is not None and 0 < limit < config.max_transfers:
            config.max_transfers = limit
        return config

    def _normalize_many(
        self, raw_transfers: list[dict[str, Any]], direction: str
    ) -> tuple[list[BlockchainTransfer], int]:
        """Normalize raw transfer rows, skipping malformed records.

        Real provider feeds occasionally contain rows that cannot be normalized
        (e.g. contract-creation / mint records with no sender or receiver).
        Those rows are skipped and counted so one bad record cannot fail the
        whole wallet query. Returns ``(transfers, skipped_count)``.
        """
        results: list[BlockchainTransfer] = []
        skipped = 0
        for raw in raw_transfers:
            try:
                results.append(self._normalize_one(raw, direction))
            except (KeyError, TypeError, ValueError):
                skipped += 1
        return results, skipped

    def _normalize_one(self, raw: dict[str, Any], direction: str) -> BlockchainTransfer:
        raw_from = (raw.get("from") or "").lower()
        raw_to = (raw.get("to") or "").lower()
        if not raw_from or not raw_to:
            raise ValueError("transfer missing from/to address")

        asset = raw.get("asset") or "ETH"
        parsed_value = raw.get("value")
        value_str = self._value_to_string(parsed_value)

        block_num = raw.get("blockNum")
        try:
            block_number = int(block_num, 16) if block_num and str(block_num).startswith("0x") else int(block_num)
        except (TypeError, ValueError):
            block_number = None

        raw_timestamp = raw.get("metadata", {}).get("blockTimestamp") if isinstance(raw.get("metadata"), dict) else None
        block_timestamp = _parse_timestamp(raw_timestamp)

        # ERC20-specific raw fields.
        erc721_area = raw.get("erc721TokenData")
        raw_contract_address = None
        raw_contract_value = None
        if "rawContract" in raw:
            raw_contract = raw["rawContract"]
            if isinstance(raw_contract, dict):
                raw_contract_address = raw_contract.get("address")
                raw_contract_value = raw_contract.get("value")
        category = raw.get("category") or "external"
        if erc721_area is not None:
            category = "erc721"

        return BlockchainTransfer(
            transaction_hash=raw.get("hash") or "",
            block_number=block_number,
            block_timestamp=block_timestamp,
            from_address=raw_from,
            to_address=raw_to,
            value=value_str,
            asset=asset or ("ERC-20" if category == "erc20" else "ETH"),
            category=category,
            direction=direction,
            raw_contract_address=raw_contract_address,
            raw_contract_value=raw_contract_value,
            chain=CHAIN_ID,
        )

    @staticmethod
    def _value_to_string(value: Any) -> str:
        """Render a provider transfer value as a stable decimal string.

        ``alchemy_getAssetTransfers`` can return ``value`` either as a raw
        scalar or as ``{"hex": ..., "decimal": ...}``. Prefer the exact decimal
        string when present; otherwise fall back to hex->decimal, preserving
        precision instead of printing a Python dict repr.
        """
        if value is None:
            return "0"
        if isinstance(value, dict):
            decimal = value.get("decimal")
            if decimal is not None:
                return str(decimal)
            hex_value = value.get("hex")
            if hex_value:
                try:
                    return str(int(str(hex_value), 16))
                except ValueError:
                    pass
        return str(value)

    def _deduplicate(self, transfers: list[BlockchainTransfer]) -> list[BlockchainTransfer]:
        seen: set[tuple] = set()
        unique: list[BlockchainTransfer] = []
        for transfer in transfers:
            key = transfer.dedup_key()
            if key in seen:
                continue
            seen.add(key)
            unique.append(transfer)
        return unique

    @staticmethod
    def _sort_key(transfer: BlockchainTransfer) -> tuple:
        ts = transfer.block_timestamp or datetime.fromtimestamp(0, tz=timezone.utc)
        block = transfer.block_number if transfer.block_number is not None else 0
        return (ts.isoformat(), block, transfer.transaction_hash)


def _parse_timestamp(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
