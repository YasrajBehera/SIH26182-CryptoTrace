"""Ronin blockchain provider.

What is real here
-----------------
Ronin publishes **no first-party REST API** for arbitrary-address history:
``Ronin.Rest`` was shut down on 2023-07-17 and Sky Mavis Skynet is being sunset.
The officially documented mechanisms are:

1. **Official public JSON-RPC** - ``https://api.roninchain.com/rpc``
   (chain id ``2020``). Confirmed working: ``eth_chainId``, ``eth_blockNumber``,
   ``eth_getBlockByNumber``, ``eth_getTransactionReceipt``, ``eth_getLogs`` and
   ``eth_call``. Documented constraints: ``eth_getLogs`` refuses ranges wider
   than 200 blocks, and non-whitelisted methods return an HTTP 400
   ``{"message": "Method is not whitelist: ..."}`` body.
2. **Alchemy's documented Ronin network** (``ronin-mainnet.g.alchemy.com``),
   which serves ``alchemy_getAssetTransfers``. Ronin must be enabled for the
   Alchemy app; until then the endpoint answers 403.

Both are implemented as :class:`RoninProvider` transports. Nothing here invents
an endpoint, a transaction hash, or a token list.

Coverage honesty
----------------
``alchemy`` transport  -> full history, native RON *and* tokens (``LIVE``).
``ronin-rpc`` transport -> real token ``Transfer`` events (ERC-20/721/1155)
discovered inside a bounded recent block window. ``eth_getLogs`` on Ronin does
return ``transactionHash``, which is used directly; block receipts are read only
as a fallback for logs that omit it. Native RON transfers have no log and are not
indexed by the public RPC, so they are NOT covered. That gap is reported in
``ProviderResult.limitations`` and the status is ``LIVE_PARTIAL``, never ``LIVE``.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from blockchain.alchemy_client import AlchemyAPIError, AlchemyClient, AlchemyHTTPError
from blockchain.chains import resolve_chain, validate_address_for_chain
from blockchain.errors import (
    InvalidAddressError,
    LiveDataUnavailableError,
    ProviderNotConfiguredError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from blockchain.models import BlockchainTransfer
from blockchain.providers import (
    SOURCE_LIVE,
    STATUS_LIVE,
    STATUS_LIVE_PARTIAL,
    STATUS_NO_DATA,
    BlockchainProvider,
    ProviderResult,
)

CHAIN_ID = "ronin"

#: Recipient used by the network for value burns; it is not a real wallet.
_ZERO_ADDRESS = "0x" + "0" * 40

#: Officially documented Ronin mainnet endpoint (docs.roninchain.com/developers/network).
DEFAULT_RPC_URL = "https://api.roninchain.com/rpc"
DEFAULT_EVM_CHAIN_ID = "2020"
DEFAULT_ALCHEMY_BASE = "https://ronin-mainnet.g.alchemy.com/v2"

#: Hard limit observed on the official public endpoint: ``eth_getLogs`` rejects
#: any range wider than exactly this many blocks with "Invalid params".
RPC_MAX_BLOCK_RANGE = 200

#: Canonical EVM event signatures. topic0 -> token standard.
TRANSFER_TOPICS: Dict[str, str] = {
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef": "erc20",
    "0x17307eab39ab6107e8899845ad3d59bd9653f200f220920489ca2b5937696c31": "erc721",
    "0xc3d58168c5ae7397731d063d5bbf3d657854427343f4c083240f7aacaa2d0f62": "erc1155_single",
    "0x4a39dc06d4c0bc64b6a4e98e34feffc5c4277f4c4c0d7fd3451b26b6bd8d0f2a": "erc1155_batch",
}

_CATEGORY_BY_STANDARD = {
    "erc20": "erc20",
    "erc721": "erc721",
    "erc1155_single": "erc1155",
    "erc1155_batch": "erc1155",
}

#: Log filters used for discovery, applied as OR'd topic0 arrays where the
#: standard allows it so one request covers several token standards.
#:
#: A ``Transfer`` event encodes ``(from, to)`` in ``topic1``/``topic2``, so the
#: wallet has to be matched in BOTH positions: a single ``[topic0, wallet]``
#: filter only ever finds *outgoing* transfers and silently misses every
#: incoming one. ERC-1155 batch transfers put the operator in ``topic1`` and the
#: recipient in ``topic2``, so they need their own filter to catch outgoing
#: batches.
#:
#: These are the topic0 **hashes** (the keys of ``TRANSFER_TOPICS``), never the
#: category names stored as its values: an OR-array of category names such as
#: ``["erc20", ...]`` is a syntactically valid filter that matches no event at
#: all, which looks exactly like an inactive wallet.
_TOPIC_ERC20 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
_TOPIC_ERC721 = "0x17307eab39ab6107e8899845ad3d59bd9653f200f220920489ca2b5937696c31"
_TOPIC_ERC1155_SINGLE = "0x4a39dc06d4c0bc64b6a4e98e34feffc5c4277f4c4c0d7fd3451b26b6bd8d0f2a"
_TOPIC_ERC1155_BATCH = "0xc3d58168c5ae7397731d063d5bbf3d657854427343f4c083240f7aacaa2d0f62"

_T20_721_1155S = [_TOPIC_ERC20, _TOPIC_ERC721, _TOPIC_ERC1155_SINGLE]
_T1155B = _TOPIC_ERC1155_BATCH

#: ``(label, topic-spec-builder)`` pairs. Each builder receives the wallet's
#: 32-byte topic and returns the ``topics`` array for that request.
LOG_FILTERS: Tuple[Tuple[str, Any], ...] = (
    ("outgoing_standard", lambda w: [_T20_721_1155S, w]),
    ("incoming_standard", lambda w: [_T20_721_1155S, None, w]),
    ("outgoing_erc1155_batch", lambda w: [[_T1155B], w, None]),
)

# ERC-20 `symbol()` / `decimals()` selectors used to label token transfers.
_SELECT_SYMBOL = "0x95d89b41"
_SELECT_DECIMALS = "0x313ce567"
_SELECT_NAME = "0x06fdde03"

MAX_SCAN_BLOCKS = 5_000_000
DEFAULT_SCAN_BLOCKS = 100_000

#: Ceiling on JSON-RPC calls spent on one official-RPC investigation. The scan
#: walks newest-first and stops as soon as enough matching events are collected,
#: so a busy wallet resolves after a handful of chunks while an inactive one
#: degrades into a disclosed partial range instead of hammering the endpoint.
DEFAULT_MAX_REQUESTS = 180

#: Parallel in-flight RPC calls. Measured against the official public endpoint:
#: 2 concurrent calls succeed (~3.8 req/s), while 4 intermittently hang until
#: the request timeout, so 2 is the safe default and higher values are opt-in.
DEFAULT_CONCURRENCY = 2

#: Native RON transfers are not indexed by any log, so they cost one block fetch
#: per block. They are therefore scanned over their own, separately bounded
#: window rather than the whole token window.
DEFAULT_NATIVE_SCAN_BLOCKS = 1_000

#: Upper bound on receipts read per matched block while mapping log positions to
#: transaction hashes. Keeps official-RPC investigations bounded in wall time on
#: busy blocks; unresolvable events are reported, never invented.
MAX_RECEIPTS_PER_BLOCK = 150


def _int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        text = str(value)
        return int(text, 16) if text.startswith("0x") else int(text)
    except (TypeError, ValueError):
        return None


def _topic_address(topic: Optional[str]) -> Optional[str]:
    if not topic or len(topic) < 42:
        return None
    return "0x" + topic[-40:].lower()


def _humanize(raw: int, decimals: int) -> str:
    """Render an integer token amount as a decimal string without float error."""
    if decimals <= 0:
        return str(raw)
    sign = "-" if raw < 0 else ""
    raw = abs(raw)
    digits = str(raw).rjust(decimals + 1, "0")
    whole, frac = digits[:-decimals], digits[-decimals:]
    frac = frac.rstrip("0")
    return f"{sign}{whole}.{frac}" if frac else f"{sign}{whole}"


def _decode_abi_string(hexdata: Optional[str]) -> Optional[str]:
    """Decode a solidity ``string`` return value (handles string and bytes32)."""
    if not hexdata or hexdata == "0x":
        return None
    raw = bytes.fromhex(hexdata[2:])
    try:
        if len(raw) == 32:
            return raw.rstrip(b"\x00").decode("utf-8", "ignore").strip() or None
        if len(raw) >= 64:
            offset = int.from_bytes(raw[0:32], "big")
            length = int.from_bytes(raw[offset : offset + 32], "big")
            return raw[offset + 32 : offset + 32 + length].decode("utf-8", "ignore").strip() or None
    except (ValueError, IndexError):
        return None
    return None


class RoninRpcClient:
    """Thin JSON-RPC client for the official public Ronin endpoint.

    The public endpoint is aggressively rate-limited (concurrent bursts get the
    connection reset), so requests are serialized and retried with backoff.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        *,
        timeout: float = 20.0,
        client: Optional[httpx.AsyncClient] = None,
        max_retries: int = 3,
        concurrency: int = DEFAULT_CONCURRENCY,
    ) -> None:
        self._url = (url or os.environ.get("RONIN_RPC_URL") or DEFAULT_RPC_URL).strip()
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None
        self._max_retries = max_retries
        # A small semaphore rather than a mutex: the public endpoint resets the
        # connection on large bursts, so requests are parallelised only up to a
        # modest in-flight limit. Backoff still needs to stay sequential.
        self._gate = asyncio.Semaphore(max(1, int(concurrency)))
        self._backoff_lock = asyncio.Lock()

    @property
    def url(self) -> str:
        return self._url

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self._timeout))
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
        self._client = None

    async def call(self, method: str, params: List[Any]) -> Any:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        last: Optional[Exception] = None
        for attempt in range(self._max_retries):
            async with self._gate:
                client = await self._get_client()
                try:
                    response = await client.post(self._url, json=payload)
                except httpx.TimeoutException as exc:
                    last = ProviderTimeoutError(
                        f"Ronin RPC timed out on {method}.", chain=CHAIN_ID
                    )
                    raise last from exc
                except httpx.HTTPError as exc:
                    last = ProviderResponseError(
                        f"Ronin RPC unreachable on {method}: {type(exc).__name__}.",
                        chain=CHAIN_ID,
                    )
                    raise last from exc

            if response.status_code == 429:
                last = ProviderRateLimitError(
                    "Ronin RPC rate limit reached.", chain=CHAIN_ID
                )
            elif response.status_code == 400:
                # Documented behaviour for methods outside the public whitelist.
                try:
                    body = response.json()
                except ValueError:
                    body = {}
                message = body.get("message") or "Invalid params"
                last = ProviderResponseError(
                    f"Ronin RPC rejected {method}: {message}", chain=CHAIN_ID
                )
            elif response.status_code != 200:
                last = ProviderResponseError(
                    f"Ronin RPC returned HTTP {response.status_code} for {method}.",
                    chain=CHAIN_ID,
                )
            else:
                try:
                    body = response.json()
                except ValueError as exc:
                    last = ProviderResponseError(
                        f"Ronin RPC returned a non-JSON body for {method}.",
                        chain=CHAIN_ID,
                    )
                    raise last from exc
                if isinstance(body, dict) and body.get("error"):
                    err = body["error"] or {}
                    text = err.get("message") or "unknown RPC error"
                    if "rate limit" in str(text).lower():
                        last = ProviderRateLimitError(
                            f"Ronin RPC rate limit: {text}", chain=CHAIN_ID
                        )
                    else:
                        last = ProviderResponseError(
                            f"Ronin RPC error on {method}: {text}", chain=CHAIN_ID
                        )
                else:
                    return body.get("result") if isinstance(body, dict) else body

            if attempt < self._max_retries - 1:
                # Serialised backoff so a rate-limited burst does not retry in
                # lockstep and deepen the throttle.
                async with self._backoff_lock:
                    await asyncio.sleep(0.4 * (attempt + 1))
        assert last is not None
        raise last

    async def chain_id(self) -> Optional[int]:
        return _int(await self.call("eth_chainId", []))

    async def block_number(self) -> int:
        value = _int(await self.call("eth_blockNumber", []))
        if value is None:
            raise ProviderResponseError(
                "Ronin RPC returned an unreadable head block.", chain=CHAIN_ID
            )
        return value

    async def get_logs(self, params: Dict[str, Any]) -> List[dict]:
        result = await self.call("eth_getLogs", [params])
        if result is None:
            return []
        if not isinstance(result, list):
            raise ProviderResponseError(
                "Ronin eth_getLogs returned an unexpected shape.", chain=CHAIN_ID
            )
        return [item for item in result if isinstance(item, dict)]

    async def block_with_transactions(self, block_number: int) -> Optional[dict]:
        result = await self.call("eth_getBlockByNumber", [hex(block_number), True])
        return result if isinstance(result, dict) else None

    async def receipt(self, tx_hash: str) -> Optional[dict]:
        result = await self.call("eth_getTransactionReceipt", [tx_hash])
        return result if isinstance(result, dict) else None

    async def eth_call(self, to: str, data: str) -> Optional[str]:
        try:
            result = await self.call("eth_call", [{"to": to, "data": data}, "latest"])
        except ProviderResponseError:
            # Non-contract address or reverting call: expected for NFTs.
            return None
        return result if isinstance(result, str) else None

    async def verify_chain(self, expected: Optional[str] = None) -> str:
        """Assert the endpoint really is Ronin before returning any data."""
        want = (expected or os.environ.get("RONIN_CHAIN_ID") or DEFAULT_EVM_CHAIN_ID).strip()
        want_int = _int(want)
        got = await self.chain_id()
        if got is None or (want_int is not None and got != want_int):
            raise ProviderResponseError(
                f"Configured Ronin endpoint reports chain id {got}, expected {want}.",
                chain=CHAIN_ID,
            )
        return str(got)


class RoninProvider(BlockchainProvider):
    """Real Ronin transfers via the official RPC or Alchemy's Ronin network."""

    chain_name = CHAIN_ID
    provider_name = "ronin"

    def __init__(
        self,
        *,
        rpc_client: Optional[RoninRpcClient] = None,
        alchemy_client: Optional[AlchemyClient] = None,
        alchemy_base_url: Optional[str] = None,
        scan_blocks: Optional[int] = None,
        timeout: float = 20.0,
    ) -> None:
        self._rpc = rpc_client
        self._alchemy = alchemy_client
        self._alchemy_base_url = alchemy_base_url
        self._scan_blocks = scan_blocks
        self._timeout = timeout
        self._token_meta: Dict[str, Tuple[str, int]] = {}
        self._block_ts: Dict[int, datetime] = {}

    # -- configuration -------------------------------------------------------

    @staticmethod
    def _alchemy_key() -> str:
        return (
            os.environ.get("RONIN_ALCHEMY_API_KEY")
            or os.environ.get("ALCHEMY_API_KEY")
            or ""
        ).strip()

    @staticmethod
    def _rpc_enabled() -> bool:
        return (os.environ.get("RONIN_RPC_ENABLED") or "true").strip().lower() not in {
            "false",
            "0",
            "no",
            "off",
        }

    def _scan_window(self) -> int:
        raw = self._scan_blocks or os.environ.get("RONIN_SCAN_BLOCKS")
        try:
            value = int(raw) if raw else DEFAULT_SCAN_BLOCKS
        except (TypeError, ValueError):
            value = DEFAULT_SCAN_BLOCKS
        return max(1, min(value, MAX_SCAN_BLOCKS))

    def _request_budget(self) -> int:
        """Maximum JSON-RPC calls this investigation may spend on log scanning."""
        raw = os.environ.get("RONIN_MAX_REQUESTS")
        try:
            value = int(raw) if raw else DEFAULT_MAX_REQUESTS
        except (TypeError, ValueError):
            value = DEFAULT_MAX_REQUESTS
        return max(len(TRANSFER_TOPICS), value)

    def _native_scan_window(self) -> int:
        """Block window for native RON discovery (one block fetch per block)."""
        raw = os.environ.get("RONIN_NATIVE_SCAN_BLOCKS")
        try:
            value = int(raw) if raw else DEFAULT_NATIVE_SCAN_BLOCKS
        except (TypeError, ValueError):
            value = DEFAULT_NATIVE_SCAN_BLOCKS
        return max(1, min(value, MAX_SCAN_BLOCKS))

    @property
    def _concurrency(self) -> int:
        raw = os.environ.get("RONIN_RPC_CONCURRENCY")
        try:
            return max(1, min(int(raw), 8)) if raw else DEFAULT_CONCURRENCY
        except (TypeError, ValueError):
            return DEFAULT_CONCURRENCY

    def describe_transports(self) -> List[str]:
        available = []
        if self._alchemy_key():
            available.append("alchemy")
        if self._rpc is not None or self._rpc_enabled():
            available.append("ronin-rpc")
        return available

    def is_configured(self) -> bool:
        return bool(self.describe_transports())

    # -- transport 1: Alchemy's documented Ronin network ---------------------

    async def _alchemy_transfers(
        self, address: str, limit: Optional[int]
    ) -> ProviderResult:
        key = self._alchemy_key()
        if not key:
            raise ProviderNotConfiguredError(CHAIN_ID)
        if self._alchemy is None:
            base = (self._alchemy_base_url or f"{DEFAULT_ALCHEMY_BASE}/{{key}}").format(key=key)
            self._alchemy = AlchemyClient(api_key=key, base_url=base, timeout=self._timeout)

        raw_directions: List[Tuple[str, List[dict]]] = []
        try:
            raw_directions.append(("out", await self._alchemy.get_transfers(address, direction="from")))
            raw_directions.append(("in", await self._alchemy.get_transfers(address, direction="to")))
        except AlchemyHTTPError as exc:
            message = str(exc)
            if "403" in message:
                raise ProviderNotConfiguredError(
                    CHAIN_ID,
                    "Alchemy key is not enabled for Ronin mainnet. Enable the "
                    "RONIN_MAINNET network for your Alchemy app, or set "
                    "RONIN_RPC_ENABLED=true to use the official Ronin RPC.",
                ) from exc
            raise ProviderResponseError(message, chain=CHAIN_ID) from exc
        except AlchemyAPIError as exc:
            raise ProviderResponseError(str(exc), chain=CHAIN_ID) from exc

        transfers: List[BlockchainTransfer] = []
        seen = set()
        for direction, rows in raw_directions:
            for raw in rows or []:
                transfer = self._normalize_alchemy(raw, address, direction)
                if transfer is None:
                    continue
                key_ = transfer.dedup_key()
                if key_ in seen:
                    continue
                seen.add(key_)
                transfers.append(transfer)

        transfers.sort(key=lambda t: (t.block_number or 0, t.transaction_hash))
        if limit:
            transfers = transfers[-limit:]

        limitations = []
        if not transfers:
            limitations.append(
                "Alchemy returned no Ronin transfers for this address."
            )
        return ProviderResult(
            chain=CHAIN_ID,
            address=address,
            data_source=SOURCE_LIVE,
            status=STATUS_LIVE if transfers else "NO_DATA",
            provider="alchemy-ronin",
            transfers=transfers,
            limitations=limitations,
        )

    def _normalize_alchemy(
        self, raw: Dict[str, Any], wallet: str, direction: str
    ) -> Optional[BlockchainTransfer]:
        tx_hash = raw.get("hash") or raw.get("transactionHash")
        sender = (raw.get("from") or "").lower()
        receiver = (raw.get("to") or "").lower()
        if not tx_hash or not sender or not receiver:
            return None
        category = raw.get("category") or "external"
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        timestamp = None
        if metadata.get("blockTimestamp"):
            try:
                timestamp = datetime.fromisoformat(
                    str(metadata["blockTimestamp"]).replace("Z", "+00:00")
                )
            except ValueError:
                timestamp = None
        raw_contract = raw.get("rawContract") if isinstance(raw.get("rawContract"), dict) else {}
        return BlockchainTransfer(
            transaction_hash=str(tx_hash),
            block_number=_int(raw.get("blockNum") or raw.get("blockNumber")),
            block_timestamp=timestamp,
            from_address=sender,
            to_address=receiver,
            value=str(raw.get("value") if raw.get("value") is not None else "0"),
            asset=str(raw.get("asset") or "RON"),
            category=str(category),
            direction=direction,
            raw_contract_address=(
                str(raw_contract["address"]).lower() if raw_contract.get("address") else None
            ),
            raw_contract_value=(
                str(raw_contract["value"]) if raw_contract.get("value") is not None else None
            ),
            chain=CHAIN_ID,
        )

    # -- transport 2: official public Ronin RPC ------------------------------

    async def _rpc_transfers(self, address: str, limit: Optional[int]) -> ProviderResult:
        if not self._rpc_enabled():
            raise ProviderNotConfiguredError(
                CHAIN_ID, "RONIN_RPC_ENABLED is disabled for this deployment."
            )
        if self._rpc is None:
            self._rpc = RoninRpcClient(timeout=self._timeout, concurrency=self._concurrency)
        # Never return data from a chain that is not Ronin.
        await self._rpc.verify_chain()

        head = await self._rpc.block_number()
        window = self._scan_window()
        from_block = max(0, head - window + 1)
        budget = self._request_budget()
        padded = "0x" + address[2:].rjust(64, "0")

        limitations: List[str] = []
        # Walks the window newest -> oldest so a recently active wallet resolves
        # after a couple of chunks, and the request budget is spent on the most
        # relevant blocks first. The chunk budget is divided across the token
        # standards, otherwise the first ERC-20 topic would consume it all.
        topics = list(TRANSFER_TOPICS)
        max_chunks = max(1, budget // len(LOG_FILTERS))
        all_chunks = list(_chunk_range_newest_first(from_block, head))
        chunks = all_chunks[:max_chunks]
        # A scan is only "complete" if it can actually reach the oldest block the
        # caller asked for. When the request budget is smaller than the window,
        # the truncation is an early stop and must be disclosed as one, otherwise
        # a 40k-block slice of a 100k-block window would be reported as though the
        # whole window had been searched.
        window_fully_plannable = len(all_chunks) <= max_chunks

        # Discovery walks chunk by chunk (newest first) rather than firing the
        # whole window at once, so it can stop as soon as enough events are found
        # and never keeps more than one chunk in flight against the public RPC.
        stop_after = max(int(limit or 0), 1)
        logs: List[dict] = []
        seen_logs = set()
        spent = 0
        scanned_to = head
        # Whether the window was searched to its end, or stopped early (budget,
        # enough results, or the endpoint throttling us). An early stop is always
        # disclosed rather than silently reported as a complete answer.
        scan_complete = True
        for chunk_start, chunk_end in chunks:
            try:
                batches = await asyncio.gather(
                    *(
                        self._rpc.get_logs(
                            {
                                "fromBlock": hex(chunk_start),
                                "toBlock": hex(chunk_end),
                                "topics": spec(padded),
                            }
                        )
                        for _label, spec in LOG_FILTERS
                    )
                )
            except LiveDataUnavailableError as exc:
                # The public endpoint stalls and throttles under sustained load.
                # Losing the tail of a deep scan must degrade into a disclosed
                # partial result, not discard real activity already collected.
                limitations.append(
                    f"Scan stopped early at block {chunk_start}: the official Ronin "
                    f"RPC became unavailable ({type(exc).__name__}). Blocks newer "
                    f"than {chunk_start} were searched; older blocks were not."
                )
                scan_complete = False
                break
            spent += len(LOG_FILTERS)
            for batch in batches:
                for log in batch or []:
                    # Overlapping filters (an ERC-1155 batch where the wallet is
                    # both operator and recipient) can match twice.
                    key = (
                        _int(log.get("blockNumber")),
                        log.get("transactionHash"),
                        _int(log.get("logIndex")),
                    )
                    if key in seen_logs:
                        continue
                    seen_logs.add(key)
                    logs.append(log)
            scanned_to = chunk_start
            if len(logs) >= stop_after:
                scan_complete = window_fully_plannable and chunk_start == chunks[-1][0]
                break
        else:
            # The loop ran out of chunks without hitting the result limit. If the
            # chunk list itself was truncated by the request budget, the window was
            # still not searched to its end.
            scan_complete = window_fully_plannable

        native_transfers, native_scanned_to = await self._native_transfers(
            address, head, budget=max(1, spent // len(LOG_FILTERS))
        )

        scanned_from = scanned_to
        if not logs and not native_transfers:
            # "Nothing found" is only ever a statement about the scanned range,
            # never about the wallet. The exact window is disclosed so nobody
            # reads an empty bounded scan as proof of inactivity.
            #
            # The official public RPC answers a throttled request with an EMPTY
            # result rather than an error, which is indistinguishable from "no
            # activity" unless it is checked. See
            # :meth:`_filters_are_functional` for the self-check that separates
            # "the endpoint is throttling us" from "our filters match nothing".
            filters_verified = await self._filters_are_functional(chunks)
            detail = (
                "The configured scan window was searched to its end."
                if scan_complete
                else "The scan did NOT reach the end of the configured window, "
                "so activity older than the blocks listed above may exist."
            )
            notes = [
                f"No ERC-20/721/1155 Transfer events and no native RON "
                f"transfers were found for this address in the scanned range "
                f"(blocks {scanned_from}-{head}, {head - scanned_from + 1} of "
                f"{head + 1} blocks). {detail}",
                "Absence of activity inside a bounded scanned range is not "
                "evidence that the wallet is inactive on Ronin.",
                *_head_continues(limitations),
            ]
            if not filters_verified:
                notes.append(
                    "This empty result could NOT be validated: a control query "
                    "using the same filters failed to match a log that the "
                    "unfiltered query had just returned, so the official RPC was "
                    "throttling us. A full history requires an indexer."
                )
            # An empty result is only a completed search ("NO_DATA") when the
            # window was actually walked to its end AND the filters were proven
            # to match real logs. If the scan was cut short or the filters could
            # not be validated, we cannot distinguish "quiet wallet" from
            # "throttled endpoint", so reporting NO_DATA would be a false claim.
            if scan_complete and filters_verified:
                status = STATUS_NO_DATA
            else:
                status = STATUS_LIVE_PARTIAL
                notes.append(
                    "The scan was incomplete or unverifiable, so this empty "
                    "result is reported as LIVE_PARTIAL rather than NO_DATA: it "
                    "must NOT be read as evidence that the wallet has no activity."
                )
            return ProviderResult(
                chain=CHAIN_ID,
                address=address,
                data_source=SOURCE_LIVE,
                status=status,
                provider="ronin-rpc",
                transfers=[],
                truncated=True,
                limitations=notes,
            )

        hashes = await self._resolve_transaction_hashes(logs)
        transfers: List[BlockchainTransfer] = []
        unresolved = 0
        for log in logs:
            transfer = await self._transfer_from_log(log, address, hashes)
            if transfer is None:
                unresolved += 1
                continue
            transfers.append(transfer)
        transfers.extend(native_transfers)

        transfers.sort(key=lambda t: (t.block_number or 0, t.transaction_hash))
        deduped: List[BlockchainTransfer] = []
        seen = set()
        for transfer in transfers:
            key = transfer.dedup_key()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(transfer)
        if limit:
            deduped = deduped[-limit:]

        limitations.append(
            _range_limitation(
                f"Scanned blocks {scanned_from}-{head} of {head + 1} "
                f"({head - scanned_from + 1} blocks searched).",
                scanned_from,
                head,
            )
        )
        if not scan_complete and not any("stopped early" in n for n in limitations):
            limitations.append(
                "The scan stopped before reaching the end of the configured "
                "window; older blocks were not searched."
            )
        if native_scanned_to is not None:
            limitations.append(
                f"Native RON transfers were scanned over blocks "
                f"{native_scanned_to}-{head} only; native transfers older than "
                "that range are not included."
            )
        if unresolved:
            limitations.append(
                f"{unresolved} event(s) could not be mapped to a transaction hash "
                "and were excluded rather than reported with an invented hash."
            )

        return ProviderResult(
            chain=CHAIN_ID,
            address=address,
            data_source=SOURCE_LIVE,
            status=STATUS_LIVE_PARTIAL,
            provider="ronin-rpc",
            transfers=deduped,
            truncated=scanned_from > 0,
            limitations=limitations,
        )

    async def _filters_are_functional(self, chunks: List[Tuple[int, int]]) -> bool:
        """Prove the discovery filters still work, or report that they do not.

        The official endpoint answers a throttled ``eth_getLogs`` call with an
        EMPTY list instead of an error. That is indistinguishable from "this
        wallet never transacted", so an empty scan is validated against a
        positive control: take a real log from an unfiltered query over the
        newest scanned chunk, then re-query the same range with the same filter
        form using that log's own ``topic1`` address.

        * control has no logs at all -> the empty answer is indistinguishable from a
          throttled endpoint serving us nothing, so the result cannot be
          trusted. This is deliberately conservative: an event-free block range
          is reported as unverified rather than assumed genuine;
        * the filtered re-query misses a log the unfiltered query returned -> the
          filters themselves are broken.

        Returns ``True`` when the filters demonstrably work.
        """
        if not chunks or self._rpc is None:
            return False
        first, last = chunks[0]
        span = {"fromBlock": hex(first), "toBlock": hex(last)}
        try:
            control = await self._rpc.get_logs(
                {**span, "topics": [list(TRANSFER_TOPICS)]}
            )
        except LiveDataUnavailableError:
            return False
        if not control:
            # A busy chain always has transfers here; getting none means we
            # cannot tell a quiet range from a throttled endpoint, so we refuse
            # to certify the empty result.
            return False

        for log in control:
            topics = log.get("topics") or []
            if len(topics) < 3:
                continue
            topic0 = str(topics[0]).lower()
            if topic0 not in TRANSFER_TOPICS:
                continue
            probe = _topic_address(str(topics[1]))
            if not probe:
                continue
            padded = "0x" + probe[2:].rjust(64, "0")
            spec = LOG_FILTERS[0][1](padded)
            try:
                matched = await self._rpc.get_logs({**span, "topics": spec})
            except LiveDataUnavailableError:
                return False
            if matched:
                return True
        return False

    async def _native_transfers(
        self, address: str, head: int, *, budget: int
    ) -> Tuple[List[BlockchainTransfer], Optional[int]]:
        """Discover native RON transfers by reading recent blocks.

        Native transfers emit no log, so the only way to find them on the public
        endpoint is to read the transactions of each block. That costs one
        request per block, so the walk is newest-first, bounded by ``budget``,
        and stopped as soon as the caller's limit is satisfied. The lowest block
        actually inspected is returned so the caller can disclose the range.
        """
        window = self._native_scan_window()
        first = max(0, head - window + 1)
        wanted = address.lower()
        found: List[BlockchainTransfer] = []
        scanned_to: Optional[int] = None
        spent = 0

        for block_number in range(head, first - 1, -1):
            if spent >= budget:
                break
            spent += 1
            try:
                block = await self._rpc.block_with_transactions(block_number)
            except LiveDataUnavailableError:
                # Native discovery is supplementary; a throttled block fetch
                # ends the walk and is disclosed instead of failing the case.
                scanned_to = block_number + 1
                break
            scanned_to = block_number
            if not block:
                continue
            self._cache_block_timestamp(block)
            for tx in block.get("transactions") or []:
                sender = str(tx.get("from") or "").lower()
                receiver = str(tx.get("to") or "").lower()
                if sender != wanted and receiver != wanted:
                    continue
                tx_hash = tx.get("hash")
                if not tx_hash:
                    # Never invent a transaction hash.
                    continue
                if not receiver or receiver == _ZERO_ADDRESS:
                    # Contract creation (no recipient) moves no RON to anyone.
                    continue
                raw_value = _int(tx.get("value")) or 0
                if raw_value <= 0:
                    # A zero-value call such as ERC-20 ``transfer()`` is a token
                    # transfer already discovered via logs. Counting it as native
                    # RON would double-count the same movement as two assets.
                    continue
                found.append(
                    BlockchainTransfer(
                        transaction_hash=tx_hash,
                        block_number=block_number,
                        block_timestamp=self._block_ts.get(block_number),
                        from_address=sender,
                        to_address=receiver,
                        value=_humanize(raw_value, 18),
                        asset="RON",
                        category="native",
                        direction="out" if sender == wanted else "in",
                        raw_contract_address=None,
                        raw_contract_value=hex(raw_value),
                        chain=CHAIN_ID,
                    )
                )
        found.sort(key=lambda t: (t.block_number or 0, t.transaction_hash))
        return found, scanned_to

    async def _resolve_transaction_hashes(self, logs: List[dict]) -> Dict[Tuple[int, int], str]:
        """Map ``(blockNumber, logIndex)`` -> real transaction hash.

        Ronin's ``eth_getLogs`` responses normally include ``transactionHash``
        for each log, in which case the mapping is free and exact. Some
        deployments omit it, and ``eth_getTransactionReceipt`` cannot be indexed
        by position, so those logs fall back to reading the receipts of the
        transactions inside each matched block. Only blocks that actually matched
        are touched, and the receipt walk stays bounded.
        """
        hashes: Dict[Tuple[int, int], str] = {}
        by_block: Dict[int, set] = {}
        for log in logs:
            block_number = _int(log.get("blockNumber"))
            log_index = _int(log.get("logIndex"))
            if block_number is None or log_index is None:
                continue
            # Trust the hash the node already returned with the log; never guess.
            direct = log.get("transactionHash")
            if direct:
                hashes[(block_number, log_index)] = str(direct)
                continue
            by_block.setdefault(block_number, set()).add(log_index)

        for block_number in sorted(by_block, reverse=True):
            try:
                block = await self._rpc.block_with_transactions(block_number)
            except LiveDataUnavailableError:
                # Mapping is best-effort; events we cannot place are reported as
                # unresolved instead of being given an invented hash.
                continue
            if not block:
                continue
            self._cache_block_timestamp(block)
            wanted = by_block[block_number]
            highest = max(wanted)
            resolved_in_block = False
            # Bounded scan: a busy Ronin block can hold hundreds of transactions
            # and the public endpoint charges one request per receipt, so the walk
            # is capped. Anything not reached is reported as unresolved rather
            # than guessed, which keeps the request time predictable.
            for examined, tx in enumerate(block.get("transactions") or []):
                if examined >= MAX_RECEIPTS_PER_BLOCK:
                    break
                tx_hash = tx.get("hash")
                if not tx_hash:
                    continue
                receipt = await self._rpc.receipt(tx_hash)
                if not receipt:
                    continue
                for entry in receipt.get("logs") or []:
                    index = _int(entry.get("logIndex"))
                    if index in wanted:
                        hashes[(block_number, index)] = receipt.get(
                            "transactionHash", tx_hash
                        )
                        resolved_in_block = True
                # Receipt logs are ordered by logIndex, so once the highest
                # wanted index is passed no later transaction can match.
                if resolved_in_block and _covers(receipt, highest):
                    break
        return hashes

    def _cache_block_timestamp(self, block: dict) -> None:
        timestamp = block.get("blockTimestamp") or block.get("timestamp")
        epoch = _int(timestamp)
        block_number = _int(block.get("number"))
        if epoch is not None and block_number is not None:
            try:
                self._block_ts[block_number] = datetime.fromtimestamp(epoch, tz=timezone.utc)
            except (ValueError, OverflowError, OSError):
                pass

    async def _transfer_from_log(
        self,
        log: dict,
        wallet: str,
        hashes: Dict[Tuple[int, int], str],
    ) -> Optional[BlockchainTransfer]:
        topics = log.get("topics") or []
        if len(topics) < 3:
            return None
        standard = TRANSFER_TOPICS.get(str(topics[0]).lower())
        if standard is None:
            return None
        sender = _topic_address(topics[1])
        receiver = _topic_address(topics[2])
        if not sender or not receiver:
            return None

        block_number = _int(log.get("blockNumber"))
        log_index = _int(log.get("logIndex"))
        tx_hash = hashes.get((block_number, log_index)) if block_number is not None else None
        if not tx_hash:
            # Never synthesize a transaction hash.
            return None

        if sender == wallet:
            direction = "out"
        elif receiver == wallet:
            direction = "in"
        else:
            return None

        contract = str(log.get("address") or "").lower()
        data = str(log.get("data") or "0x")
        raw_value = _decode_log_value(standard, data)
        symbol, decimals = await self._token_metadata(contract)

        return BlockchainTransfer(
            transaction_hash=tx_hash,
            block_number=block_number,
            block_timestamp=self._block_ts.get(block_number) if block_number is not None else None,
            from_address=sender,
            to_address=receiver,
            value=_humanize(raw_value, decimals),
            asset=symbol,
            category=_CATEGORY_BY_STANDARD[standard],
            direction=direction,
            raw_contract_address=contract or None,
            raw_contract_value=hex(raw_value),
            chain=CHAIN_ID,
        )

    async def _token_metadata(self, contract: str) -> Tuple[str, int]:
        """Resolve a token's symbol/decimals on-chain via ``eth_call``.

        ERC-1155 collections have no ``decimals()``, so the call legitimately
        reverts; the asset is then labelled by its contract instead of guessing.
        """
        if contract in self._token_meta:
            return self._token_meta[contract]
        symbol = await self._rpc.eth_call(contract, _SELECT_SYMBOL)
        decimals_raw = await self._rpc.eth_call(contract, _SELECT_DECIMALS)
        resolved_symbol = _decode_abi_string(symbol) or f"ERC1155:{contract[:10]}"
        decimals = _int(decimals_raw)
        if decimals is None or not 0 <= decimals <= 36:
            decimals = 0
        self._token_meta[contract] = (resolved_symbol, decimals)
        return self._token_meta[contract]

    # -- provider contract ---------------------------------------------------

    async def get_transfers(
        self,
        address: str,
        limit: Optional[int] = None,
    ) -> ProviderResult:
        chain = resolve_chain(self.chain_name)
        normalized_address = validate_address_for_chain(address, chain.id)

        transports: List[str] = []
        if self._alchemy_key():
            transports.append("alchemy")
        if self._rpc is not None or self._rpc_enabled():
            transports.append("rpc")

        if not transports:
            raise ProviderNotConfiguredError(
                CHAIN_ID,
                "Ronin provider is not configured. Set RONIN_RPC_ENABLED=true to "
                "use the official Ronin JSON-RPC "
                f"({DEFAULT_RPC_URL}), or set RONIN_ALCHEMY_API_KEY to a key with "
                "the Ronin mainnet network enabled. No synthetic data is "
                "substituted for Ronin investigations.",
            )

        errors: List[str] = []
        if "alchemy" in transports:
            try:
                return await self._alchemy_transfers(normalized_address, limit)
            except (ProviderNotConfiguredError, ProviderResponseError, ProviderTimeoutError,
                    ProviderRateLimitError, LiveDataUnavailableError) as exc:
                errors.append(f"alchemy-ronin: {exc}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"alchemy-ronin: unexpected {type(exc).__name__}: {exc}")

        if "rpc" in transports:
            try:
                return await self._rpc_transfers(normalized_address, limit)
            except (ProviderNotConfiguredError, ProviderResponseError, ProviderTimeoutError,
                    ProviderRateLimitError, LiveDataUnavailableError) as exc:
                errors.append(f"ronin-rpc: {exc}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"ronin-rpc: unexpected {type(exc).__name__}: {exc}")

        detail = " | ".join(errors) or "no usable transport"
        raise LiveDataUnavailableError(
            f"Live Ronin data unavailable for {normalized_address}. {detail}",
            chain=CHAIN_ID,
        )

    async def is_healthy(self) -> bool:
        if self._rpc is None and self._rpc_enabled():
            try:
                self._rpc = RoninRpcClient(timeout=5.0)
            except Exception:  # noqa: BLE001
                return False
        if self._rpc is None:
            return False
        try:
            await self._rpc.verify_chain()
            await self._rpc.block_number()
            return True
        except Exception:  # noqa: BLE001 - health probes never raise
            return False

    async def aclose(self) -> None:
        if self._rpc is not None:
            await self._rpc.aclose()
        if self._alchemy is not None:
            await self._alchemy.aclose()


def _head_continues(notes: List[str]) -> List[str]:
    """Carry over any limitation recorded before discovery finished."""
    return [note for note in notes if note]


def _range_limitation(prefix: str, scanned_from: int, head: int) -> str:
    """Describe a scanned range, flagging it as partial when it misses genesis."""
    if scanned_from > 0:
        return (
            f"{prefix} This is a bounded scan: activity older than block "
            f"{scanned_from} was not searched."
        )
    return f"{prefix} The full chain history was scanned."


def _chunk_range(first: int, last: int) -> List[Tuple[int, int]]:
    """Split ``[first, last]`` into inclusive ranges of at most RPC_MAX_BLOCK_RANGE.

    ``eth_getLogs`` on the official Ronin endpoint rejects any range wider than
    ``RPC_MAX_BLOCK_RANGE`` blocks, so a wider discovery window has to be walked
    in consecutive chunks rather than sent as one oversized request.
    """
    if last < first:
        return []
    chunks: List[Tuple[int, int]] = []
    start = first
    while start <= last:
        end = min(start + RPC_MAX_BLOCK_RANGE - 1, last)
        chunks.append((start, end))
        start = end + 1
    return chunks


def _chunk_range_newest_first(first: int, last: int) -> List[Tuple[int, int]]:
    """Like :func:`_chunk_range` but ordered newest block first.

    The official endpoint must be walked in 200-block slices, so the order in
    which those slices are visited decides how much history a request budget
    buys. Newest-first means an actively used wallet is resolved immediately
    instead of after the whole window has been crawled.
    """
    return list(reversed(_chunk_range(first, last)))


def _covers(receipt: Dict[str, Any], highest_log_index: int) -> bool:
    """True once a receipt's logs reach ``highest_log_index``.

    Lets the receipt scan stop early instead of reading every transaction in a
    matched block.
    """
    for entry in receipt.get("logs") or []:
        index = _int(entry.get("logIndex"))
        if index is not None and index >= highest_log_index:
            return True
    return False


def _decode_log_value(standard: str, data: str) -> int:
    """Extract the transferred amount from a Transfer log's data field."""
    raw = data[2:] if data.startswith("0x") else data
    if not raw:
        return 0
    try:
        if standard in ("erc20", "erc721"):
            return int(raw, 16)
        # ERC-1155 TransferSingle: (id, value). TransferBatch: (ids..., values...).
        words = [raw[i : i + 64] for i in range(0, len(raw), 64)]
        if standard == "erc1155_single" and len(words) >= 2:
            return int(words[1], 16)
        if standard == "erc1155_batch" and len(words) >= 2:
            half = len(words) // 2
            return sum(int(w, 16) for w in words[half:])
    except ValueError:
        return 0
    return 0