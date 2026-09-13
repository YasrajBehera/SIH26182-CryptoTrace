"""Blockchain service layer.

The rest of the application talks to this service instead of calling Alchemy
directly. It validates the address, fetches incoming and outgoing transfers,
combines and de-duplicates them, normalizes each transfer and returns a
``WalletTransfers`` response model sorted chronologically.
"""

from __future__ import annotations
import os
from app.config import settings
from datetime import datetime, timezone
from typing import Any, Optional

from blockchain.alchemy_client import AlchemyClient
from blockchain.models import BlockchainTransfer, PaginationInfo, WalletTransfers
from blockchain.pagination import PaginationConfig
from blockchain.validators import InvalidAddressError, validate_address

CHAIN_ID = "eth"

_NATIVE_SYMBOLS = {"ETH", "MATIC", "BNB", "AVAX", "SOL", "NATIVE"}


class BlockchainService:
    """High-level service for querying a wallet's transfer history.

    Data sourcing is explicit and consistent:
      - When persisted rows already exist for the wallet (PostgreSQL wallet
        store) they are served first (``source="database"``). Every page and
        every frontend surface then sees the SAME canonical transfer set — no
        repeated provider round-trips, no per-page variation, no timeouts.
      - ``refresh=True`` (or no persisted rows) fetches from the blockchain
        provider, normalizes, back-fills missing timestamps from the chain
        block, persists the result, and serves it (``source="provider"``).
      - Block timestamps come from the chain: ``metadata.blockTimestamp`` when
        the provider supplies it, otherwise ``eth_getBlockByNumber`` for the
        transfer's block.
    """

    def __init__(
        self,
        client: Optional[AlchemyClient] = None,
        pagination: Optional[PaginationConfig] = None,
        wallet_repository=None,
    ) -> None:
        self._client = client
        self._pagination = pagination or PaginationConfig()
        self.wallet_repository = wallet_repository

    async def get_wallet_transfers(
        self,
        wallet_address: str,
        chain: str = CHAIN_ID,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        direction: Optional[str] = None,
        refresh: bool = False,
    ) -> WalletTransfers:
        """Return a normalized, de-duplicated, chronologically sorted transfer set.

        Server-side pagination: ``limit``/``offset`` slice the sorted set held
        for the wallet, while ``total``/``has_next``/``has_previous`` are
        derived from that held set. ``direction`` may restrict to "in"/"out"
        so filters stay consistent across pages. ``refresh=True`` forces a
        fresh provider fetch instead of replaying persisted rows.
        """
        try:
            normalized_address = validate_address(wallet_address)
        except InvalidAddressError as exc:
            raise InvalidAddressError(str(exc)) from exc

        config = self._apply_overrides(limit, offset)
        offset = offset or 0
        if offset < 0:
            raise ValueError("offset must be >= 0")
        if direction not in (None, "in", "out"):
            raise ValueError("direction must be 'in' or 'out'")

        stored = self._stored_rows(normalized_address, chain)
        if stored and not refresh:
            return self._paginate_stored(
                normalized_address, chain, stored, limit, offset, direction
            )

        async with self._client or AlchemyClient(
         api_key=os.environ.get("ALCHEMY_API_KEY") or settings.alchemy_api_key,
         pagination=config,
         ) as client:
            raw_directions: list[tuple[str, list]] = []
            if direction in (None, "out"):
                raw_directions.append(("out", await client.get_transfers(normalized_address, direction="from")))
            if direction in (None, "in"):
                raw_directions.append(("in", await client.get_transfers(normalized_address, direction="to")))

            transfers: list[BlockchainTransfer] = []
            skipped = 0
            for flow_direction, raw_rows in raw_directions:
                normalized, malformed = self._normalize_many(raw_rows, flow_direction)
                transfers.extend(normalized)
                skipped += malformed

            transfers = self._deduplicate(transfers)

            # Timestamp authority: any transfer whose provider metadata lacks a
            # block timestamp is resolved from the chain block itself
            # (eth_getBlockByNumber), so block_number and block_timestamp always
            # originate from the same source.
            missing_blocks = {
                t.block_number
                for t in transfers
                if t.block_number is not None and t.block_timestamp is None
            }
            if missing_blocks:
                try:
                    from_block = await client.get_block_timestamps(
                        sorted(missing_blocks)[: self._pagination.max_pages * 50]
                    )
                    resolved = {
                        bn: _coerce_utc(ts)
                        for bn, ts in from_block.items()
                        if _coerce_utc(ts) is not None
                    }
                    transfers = [
                        t.model_copy(update={"block_timestamp": resolved[t.block_number]})
                        if t.block_number in resolved
                        else t
                        for t in transfers
                    ]
                except Exception:
                    # Available timestamps are authoritative; unresolvable ones
                    # stay None and surface as "unknown" downstream. A block
                    # resolution failure must never blank an otherwise good set.
                    pass

            transfers.sort(key=self._sort_key)

            # Only real chain data may enter the durable wallet store.
            if transfers and self.wallet_repository is not None:
                self.wallet_repository.store_transactions(
                    [self._to_wallet_row(t) for t in transfers]
                )

        max_transfers = config.max_transfers
        truncated = len(transfers) > max_transfers
        held = transfers[:max_transfers]
        total = len(held)

        page = held[offset : offset + limit] if limit else held[offset:]
        return WalletTransfers(
            wallet_address=normalized_address,
            chain=chain,
            transfers=page,
            pagination=PaginationInfo(
                max_transfers=max_transfers,
                fetched=len(page),
                truncated=truncated,
                skipped=skipped,
                offset=offset,
                limit=limit,
                total=total,
                has_next=(offset + len(page)) < total,
                has_previous=offset > 0,
                source="provider",
            ),
        )

    def _stored_rows(self, address: str, chain: str) -> list[dict]:
        """Return persisted wallet-store rows for the address, or []."""
        if self.wallet_repository is None:
            return []
        try:
            rows = self.wallet_repository.list_transactions(
                address=address, chain=chain
            )
        except Exception:
            return []
        return rows or []

    def _paginate_stored(
        self,
        address: str,
        chain: str,
        rows: list[dict],
        limit: Optional[int],
        offset: int,
        direction: Optional[str],
    ) -> WalletTransfers:
        """Serve the persisted canonical transfer set with server pagination."""
        rows = [
            r for r in rows
            if direction is None or self._row_direction(r, address) == direction
        ]
        rows.sort(
            key=lambda r: (
                int(r.get("block_timestamp") or 0),
                int(r.get("block_number") or 0),
                r.get("tx_hash") or "",
            )
        )
        total = len(rows)
        page_rows = rows[offset : offset + limit] if limit else rows[offset:]
        page = [self._row_to_transfer(r, address) for r in page_rows]
        return WalletTransfers(
            wallet_address=address,
            chain=chain,
            transfers=page,
            pagination=PaginationInfo(
                max_transfers=total,
                fetched=len(page_rows),
                truncated=False,
                skipped=0,
                offset=offset,
                limit=limit,
                total=total,
                has_next=(offset + len(page_rows)) < total,
                has_previous=offset > 0,
                source="database",
            ),
        )

    @staticmethod
    def _row_direction(row: dict, address: str) -> str:
        if (row.get("to_address") or "").lower() == address.lower():
            return "in"
        return "out"

    def _row_to_transfer(self, row: dict, address: str) -> BlockchainTransfer:
        symbol = row.get("token_symbol") or ""
        ts = row.get("block_timestamp")
        block_timestamp = None
        if ts:
            try:
                block_timestamp = datetime.fromtimestamp(int(ts), tz=timezone.utc)
            except (TypeError, ValueError, OverflowError):
                block_timestamp = None
        category = "external" if symbol.upper() in _NATIVE_SYMBOLS else "erc20"
        return BlockchainTransfer(
            transaction_hash=row.get("tx_hash") or "",
            block_number=row.get("block_number"),
            block_timestamp=block_timestamp,
            from_address=row.get("from_address") or "",
            to_address=row.get("to_address") or "",
            value=str(row.get("value") or "0"),
            asset=symbol or "ETH",
            category=category,
            direction=self._row_direction(row, address),
            raw_contract_address=None,
            raw_contract_value=None,
            chain=row.get("chain") or "eth",
        )

    def _to_wallet_row(self, transfer: BlockchainTransfer) -> dict:
        ts = transfer.block_timestamp
        ts_int = int(ts.timestamp()) if hasattr(ts, "timestamp") else 0
        return {
            "chain": transfer.chain or CHAIN_ID,
            "tx_hash": transfer.transaction_hash,
            "block_number": transfer.block_number,
            "block_timestamp": ts_int,
            "from_address": transfer.from_address,
            "to_address": transfer.to_address,
            "value": transfer.value,
            "fee": None,
            "token_symbol": transfer.asset,
        }

    def _apply_overrides(
        self,
        limit: Optional[int],
        offset: Optional[int] = None,
    ) -> PaginationConfig:
        config = PaginationConfig(
            max_pages=self._pagination.max_pages,
            max_transfers=self._pagination.max_transfers,
        )
        # Legacy callers pass a `limit` as a hard cap with no offset; keep that
        # behaviour so the set never exceeds `limit` rows. Real server-side
        # pagination passes `offset` (with or without `limit`) and pages within
        # the full provider window (bounded by the default max_transfers cap),
        # so `has_next` can point past the current page.
        if (
            limit is not None
            and offset is None
            and 0 < limit < config.max_transfers
        ):
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


def _coerce_utc(value: Any) -> Optional[datetime]:
    """Coerce a provider block timestamp (unix int, float, or datetime) to UTC.

    ``model_copy(update=...)`` applies updates without re-validation, so raw
    epoch values must be converted here before they reach
    ``BlockchainTransfer.block_timestamp`` (a datetime) or ``_sort_key`` would
    hit ``int.isoformat()``.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None
    return None
