"""Tests for the Member 1 blockchain data layer.

These tests use mocked blockchain clients and never require a real Alchemy
API key.
"""

from __future__ import annotations

from typing import Any, Optional

import pytest

from blockchain.alchemy_client import (
    AlchemyAPIError,
    AlchemyConfigError,
    AlchemyHTTPError,
)
from blockchain.models import WalletTransfers
from blockchain.pagination import PaginationConfig
from blockchain.service import BlockchainService
from blockchain.validators import InvalidAddressError, is_valid_address, validate_address


@pytest.fixture
def client(app_client):
    return app_client

VALID_ADDRESS = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
VALID_LOWER = VALID_ADDRESS.lower()


# --------------------------------------------------------------------------- #
# Fake blockchain client used to simulate Alchemy responses.
# --------------------------------------------------------------------------- #
class FakeAlchemyClient:
    def __init__(
        self,
        response_for: dict[str, list[dict[str, Any]]] | None = None,
        error: Optional[Exception] = None,
        block_timestamps: dict[int, int] | None = None,
    ) -> None:
        self._response_for = response_for or {"from": [], "to": []}
        self._error = error
        self._block_timestamps = block_timestamps or {}
        self.calls: list[tuple[str, str]] = []
        self.block_timestamp_calls: list[int] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def aclose(self) -> None:
        return None

    async def get_transfers(
        self, wallet_address: str, direction: str, categories=None
    ) -> list[dict[str, Any]]:
        self.calls.append((wallet_address, direction))
        if self._error is not None:
            raise self._error
        return list(self._response_for.get(direction, []))

    async def get_block_timestamps(
        self, block_numbers: list[int]
    ) -> dict[int, int]:
        self.block_timestamp_calls.extend(block_numbers)
        return {
            bn: ts
            for bn, ts in self._block_timestamps.items()
            if bn in set(block_numbers)
        }


def make_eth(hash_, wallet, direction="in", block="0x10"):
    counterparty = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    if direction == "out":
        from_addr, to_addr = wallet, counterparty
    else:
        from_addr, to_addr = counterparty, wallet
    return {
        "hash": hash_,
        "blockNum": block,
        "from": from_addr,
        "to": to_addr,
        "value": {"hex": "0x0", "decimal": 0},
        "asset": "ETH",
        "category": "external",
        "metadata": {"blockTimestamp": "2023-01-01T00:00:00Z"},
    }


def make_erc20(hash_, to, contract="0xcccccccccccccccccccccccccccccccccccccccc", value="1000"):
    return {
        "hash": hash_,
        "blockNum": "0x11",
        "from": "0xdddddddddddddddddddddddddddddddddddddddd",
        "to": to,
        "value": {"hex": "0x0", "decimal": 0},
        "asset": "USDT",
        "category": "erc20",
        "rawContract": {"address": contract, "value": hex(int(value))},
        "metadata": {"blockTimestamp": "2023-01-02T00:00:00Z"},
    }


@pytest.fixture
def service() -> BlockchainService:
    return BlockchainService(pagination=PaginationConfig(max_pages=20, max_transfers=1000))


# --------------------------------------------------------------------------- #
# Validators
# --------------------------------------------------------------------------- #
class TestValidators:
    def test_valid_address(self):
        assert is_valid_address(VALID_ADDRESS)
        assert is_valid_address(VALID_LOWER)
        assert validate_address(VALID_ADDRESS) == VALID_LOWER

    def test_invalid_address(self):
        # A mixed-case address with a broken EIP-55 checksum: flip the case of
        # one alphabetic character in an otherwise-valid checksum address.
        idx = next(i for i, c in enumerate(VALID_ADDRESS[2:]) if c.isalpha()) + 2
        broken_checksum = (
            VALID_ADDRESS[:idx] + VALID_ADDRESS[idx].swapcase() + VALID_ADDRESS[idx + 1 :]
        )
        assert is_valid_address(VALID_ADDRESS) is True
        assert is_valid_address(broken_checksum) is False
        for bad in [
            "",
            "0x123",
            "0x" + "g" * 40,
            "12345",
            None,
        ]:
            with pytest.raises((InvalidAddressError, TypeError)):
                validate_address(bad)


# --------------------------------------------------------------------------- #
# Service: normalization / direction / dedup / sorting
# --------------------------------------------------------------------------- #
class TestService:
    def test_incoming_parsing(self, service):
        fake = FakeAlchemyClient(
            response_for={"to": [make_eth("0x1", VALID_LOWER)], "from": []}
        )
        result: WalletTransfers = _run(service, fake, VALID_ADDRESS)
        assert len(result.transfers) == 1
        t = result.transfers[0]
        assert t.direction == "in"
        assert t.to_address == VALID_LOWER
        assert t.transaction_hash == "0x1"

    def test_outgoing_parsing(self, service):
        fake = FakeAlchemyClient(
            response_for={
                "from": [
                    {
                        "hash": "0x2",
                        "blockNum": "0x12",
                        "from": VALID_LOWER,
                        "to": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                        "value": {"hex": "0x0", "decimal": 0},
                        "asset": "ETH",
                        "category": "external",
                        "metadata": {"blockTimestamp": "2023-01-03T00:00:00Z"},
                    }
                ],
                "to": [],
            }
        )
        result = _run(service, fake, VALID_ADDRESS)
        assert len(result.transfers) == 1
        t = result.transfers[0]
        assert t.direction == "out"
        assert t.from_address == VALID_LOWER

    def test_combines_incoming_and_outgoing(self, service):
        fake = FakeAlchemyClient(
            response_for={
                "to": [make_eth("0x1", VALID_LOWER)],
                "from": [
                    {
                        "hash": "0x2",
                        "blockNum": "0x12",
                        "from": VALID_LOWER,
                        "to": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                        "value": 0,
                        "asset": "ETH",
                        "category": "external",
                        "metadata": {"blockTimestamp": "2023-01-03T00:00:00Z"},
                    }
                ],
            }
        )
        result = _run(service, fake, VALID_ADDRESS)
        assert len(result.transfers) == 2
        directions = {t.direction for t in result.transfers}
        assert directions == {"in", "out"}

    def test_duplicate_removal(self, service):
        dup = make_eth("0x1", VALID_LOWER)
        fake = FakeAlchemyClient(
            response_for={"to": [dup, dict(dup)], "from": []}
        )
        result = _run(service, fake, VALID_ADDRESS)
        assert len(result.transfers) == 1

    def test_multiple_token_transfers_same_tx_kept(self, service):
        # Two distinct erc20 transfers in the same transaction but to/from
        # different counterparties must be preserved (not wrongly deduped).
        t1 = make_erc20("0xT", "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        t2 = make_erc20("0xT", "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        fake = FakeAlchemyClient(response_for={"to": [t1, t2, dict(t1)], "from": []})
        result = _run(service, fake, VALID_ADDRESS)
        assert len(result.transfers) == 2

    def test_sort_chronological(self, service):
        older = make_eth("0x1", VALID_LOWER)
        newer = make_eth("0x2", VALID_LOWER, block="0x14")
        newer["metadata"]["blockTimestamp"] = "2023-01-05T00:00:00Z"
        fake = FakeAlchemyClient(response_for={"to": [newer, older], "from": []})
        result = _run(service, fake, VALID_ADDRESS)
        assert result.transfers[0].transaction_hash == "0x1"
        assert result.transfers[1].transaction_hash == "0x2"

    def test_empty_wallet(self, service):
        fake = FakeAlchemyClient(response_for={"to": [], "from": []})
        result = _run(service, fake, VALID_ADDRESS)
        assert result.transfers == []
        assert result.pagination.fetched == 0

    def test_malformed_rows_skipped_and_counted(self, service):
        # Real provider feeds include records with no sender/receiver (e.g.
        # contract-creation / mint rows). These must be skipped and counted,
        # not fail the whole wallet query with a 500.
        good = make_eth("0x1", VALID_LOWER)
        bad = {
            "hash": "0xbad",
            "blockNum": "0x1",
            "from": "",
            "to": "",
            "value": "1",
            "asset": "ETH",
            "category": "external",
            "metadata": {"blockTimestamp": "2023-01-01T00:00:00Z"},
        }
        fake = FakeAlchemyClient(response_for={"to": [bad, good], "from": []})
        result = _run(service, fake, VALID_ADDRESS)
        assert len(result.transfers) == 1
        assert result.transfers[0].transaction_hash == "0x1"
        assert result.pagination.skipped == 1

    def test_provider_value_dict_extracts_decimal(self, service):
        # Alchemy returns `value` as {"hex": ..., "decimal": ...}; the decimal
        # string must be surfaced verbatim rather than a dict repr.
        row = make_eth("0x9", VALID_LOWER)
        row["value"] = {"hex": "0xde0b6b3a7640000", "decimal": 1000000000000000000}
        fake = FakeAlchemyClient(response_for={"to": [row], "from": []})
        result = _run(service, fake, VALID_ADDRESS)
        assert result.transfers[0].value == "1000000000000000000"

    def test_provider_value_hex_only_falls_back_to_decimal(self, service):
        row = make_eth("0xa", VALID_LOWER)
        row["value"] = {"hex": "0xde0b6b3a7640000"}
        fake = FakeAlchemyClient(response_for={"to": [row], "from": []})
        result = _run(service, fake, VALID_ADDRESS)
        assert result.transfers[0].value == "1000000000000000000"

    def test_limit_cap(self):
        svc = BlockchainService(pagination=PaginationConfig(max_transfers=1000))
        rows = [make_eth(f"0x{i}", VALID_LOWER) for i in range(5)]
        fake = FakeAlchemyClient(response_for={"to": rows, "from": []})
        result = _run(svc, fake, VALID_ADDRESS, limit=2)
        assert len(result.transfers) == 2
        assert result.pagination.truncated is True

    def test_offset_slices_held_set(self):
        # `make_eth` rows share one timestamp, so the stable sort preserves
        # input order and slicing is deterministic.
        svc = BlockchainService(pagination=PaginationConfig(max_transfers=1000))
        rows = [make_eth(f"0x{i}", VALID_LOWER) for i in range(5)]
        fake = FakeAlchemyClient(response_for={"to": rows, "from": []})
        result = _run(svc, fake, VALID_ADDRESS, limit=2, offset=2)
        hashes = [t.transaction_hash for t in result.transfers]
        assert hashes == ["0x2", "0x3"]
        assert result.pagination.offset == 2
        assert result.pagination.total == 5
        assert result.pagination.fetched == 2
        assert result.pagination.truncated is False
        assert result.pagination.has_next is True
        assert result.pagination.has_previous is True

    def test_last_page_has_no_next(self):
        svc = BlockchainService(pagination=PaginationConfig(max_transfers=1000))
        rows = [make_eth(f"0x{i}", VALID_LOWER) for i in range(5)]
        fake = FakeAlchemyClient(response_for={"to": rows, "from": []})
        result = _run(svc, fake, VALID_ADDRESS, limit=5, offset=0)
        assert len(result.transfers) == 5
        assert result.pagination.has_next is False
        assert result.pagination.has_previous is False
        assert result.pagination.total == 5

    def test_middle_page_has_both_edges(self):
        svc = BlockchainService(pagination=PaginationConfig(max_transfers=1000))
        rows = [make_eth(f"0x{i}", VALID_LOWER) for i in range(5)]
        fake = FakeAlchemyClient(response_for={"to": rows, "from": []})
        result = _run(svc, fake, VALID_ADDRESS, limit=2, offset=2)
        assert result.pagination.has_next is True
        assert result.pagination.has_previous is True

    def test_offset_past_end_returns_empty_page(self):
        svc = BlockchainService(pagination=PaginationConfig(max_transfers=1000))
        rows = [make_eth(f"0x{i}", VALID_LOWER) for i in range(5)]
        fake = FakeAlchemyClient(response_for={"to": rows, "from": []})
        result = _run(svc, fake, VALID_ADDRESS, limit=2, offset=10)
        assert result.transfers == []
        assert result.pagination.total == 5
        assert result.pagination.has_next is False
        assert result.pagination.has_previous is True

    def test_direction_filter_fetches_only_requested_side(self):
        svc = BlockchainService(pagination=PaginationConfig(max_transfers=1000))
        incoming = [make_eth(f"0x{i}", VALID_LOWER, direction="in") for i in range(2)]
        outgoing = [make_eth(f"0x{i}", VALID_LOWER, direction="out") for i in range(3)]
        fake = FakeAlchemyClient(response_for={"to": incoming, "from": outgoing})
        result = _run(svc, fake, VALID_ADDRESS, direction="out")
        assert fake.calls == [(VALID_LOWER, "from")]
        assert len(result.transfers) == 3
        assert all(t.direction == "out" for t in result.transfers)
        assert result.pagination.total == 3

    def test_direction_filter_in_fetches_only_incoming(self):
        svc = BlockchainService(pagination=PaginationConfig(max_transfers=1000))
        incoming = [make_eth(f"0x{i}", VALID_LOWER, direction="in") for i in range(2)]
        outgoing = [make_eth(f"0x{i}", VALID_LOWER, direction="out") for i in range(3)]
        fake = FakeAlchemyClient(response_for={"to": incoming, "from": outgoing})
        result = _run(svc, fake, VALID_ADDRESS, direction="in")
        assert fake.calls == [(VALID_LOWER, "to")]
        assert all(t.direction == "in" for t in result.transfers)

    def test_direction_filter_invalid_raises(self):
        svc = BlockchainService(pagination=PaginationConfig(max_transfers=1000))
        fake = FakeAlchemyClient()
        with pytest.raises(ValueError):
            _run(svc, fake, VALID_ADDRESS, direction="sideways")

    def test_offset_negative_raises(self):
        svc = BlockchainService(pagination=PaginationConfig(max_transfers=1000))
        fake = FakeAlchemyClient()
        with pytest.raises(ValueError):
            _run(svc, fake, VALID_ADDRESS, offset=-1)

    def test_invalid_address_raises(self, service):
        fake = FakeAlchemyClient()
        with pytest.raises(InvalidAddressError):
            _run(service, fake, "not-an-address")


def _run(
    service: BlockchainService,
    fake: FakeAlchemyClient,
    address: str,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    direction: Optional[str] = None,
    refresh: bool = False,
) -> WalletTransfers:
    import asyncio

    service._client = fake
    return asyncio.run(
        service.get_wallet_transfers(
            address, limit=limit, offset=offset, direction=direction, refresh=refresh
        )
    )


# --------------------------------------------------------------------------- #
# Persisted wallet store (source="database")
# --------------------------------------------------------------------------- #
class TestPersistedTransfers:
    """Regression: transfers must be served from the persisted wallet store when
    rows already exist, so every page/surface sees the same canonical set instead
    of re-hitting the blockchain provider (which caused 502s/timeouts and
    per-page variation in the live demo).
    """

    @staticmethod
    def make_rows(address, n=5, base_ts=1700000000, base_block=1000, direction="in"):
        from wallets.repository import MemoryWalletRepository

        repo = MemoryWalletRepository()
        counterparty = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        rows = []
        for i in range(n):
            if direction == "out":
                from_addr, to_addr = address, counterparty
            else:
                from_addr, to_addr = counterparty, address
            rows.append(
                {
                    "chain": "eth",
                    "tx_hash": f"0xpersist{i:03d}",
                    "block_number": base_block + i,
                    "block_timestamp": base_ts + i,
                    "from_address": from_addr,
                    "to_address": to_addr,
                    "value": "10",
                    "fee": None,
                    "token_symbol": "ETH",
                }
            )
        repo.store_transactions(rows)
        return repo

    @staticmethod
    def svc(fake, repo=None):
        from wallets.repository import MemoryWalletRepository

        return BlockchainService(
            client=fake,
            pagination=PaginationConfig(max_pages=20, max_transfers=1000),
            wallet_repository=repo or MemoryWalletRepository(),
        )

    def test_serves_persisted_rows_without_calling_provider(self):
        repo = self.make_rows(VALID_LOWER)
        fake = FakeAlchemyClient()
        result = _run(self.svc(fake, repo), fake, VALID_ADDRESS)

        assert result.pagination.source == "database"
        assert result.pagination.total == 5
        assert len(result.transfers) == 5
        assert fake.calls == []  # provider never consulted

    def test_persisted_rows_have_chain_block_timestamps(self):
        repo = self.make_rows(VALID_LOWER)
        fake = FakeAlchemyClient()
        result = _run(self.svc(fake, repo), fake, VALID_ADDRESS)

        assert all(t.block_timestamp is not None for t in result.transfers)
        assert result.transfers[0].block_timestamp.isoformat().startswith("2023-11-14T")
        assert [t.block_number for t in result.transfers] == list(range(1000, 1005))

    def test_paginates_persisted_rows_server_side(self):
        repo = self.make_rows(VALID_LOWER, n=5)
        fake = FakeAlchemyClient()
        first = _run(self.svc(fake, repo), fake, VALID_ADDRESS, limit=2, offset=0)
        assert len(first.transfers) == 2
        assert first.pagination.total == 5
        assert first.pagination.has_next is True
        assert first.pagination.has_previous is False

        last = _run(self.svc(fake, repo), fake, VALID_ADDRESS, limit=2, offset=4)
        assert len(last.transfers) == 1
        assert last.pagination.has_next is False
        assert last.pagination.has_previous is True

    def test_direction_filter_applies_to_persisted_rows(self):
        repo = self.make_rows(VALID_LOWER, n=3, direction="in")
        repo.store_transactions(
            [
                {
                    "chain": "eth",
                    "tx_hash": "0xout001",
                    "block_number": 2000,
                    "block_timestamp": 1800000000,
                    "from_address": VALID_LOWER,
                    "to_address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                    "value": "5",
                    "fee": None,
                    "token_symbol": "ETH",
                }
            ]
        )
        fake = FakeAlchemyClient()
        out = _run(self.svc(fake, repo), fake, VALID_ADDRESS, direction="out")
        assert [t.transaction_hash for t in out.transfers] == ["0xout001"]
        assert out.pagination.total == 1
        assert all(t.direction == "out" for t in out.transfers)
        assert fake.calls == []

    def test_refresh_forces_provider_fetch_even_with_persisted_rows(self):
        repo = self.make_rows(VALID_LOWER, n=3)
        fresh = make_eth("0xfresh", VALID_LOWER, direction="in")
        fake = FakeAlchemyClient(response_for={"to": [fresh], "from": []})
        result = _run(self.svc(fake, repo), fake, VALID_ADDRESS, refresh=True)

        assert result.pagination.source == "provider"
        assert fake.calls != []
        # Provider result persisted alongside the previous rows.
        assert repo.transaction_count() == 4

    def test_provider_fetch_persists_normalized_rows(self):
        repo = self.__class__.make_rows_blank()
        incoming = [make_eth(f"0xP{i}", VALID_LOWER, direction="in") for i in range(2)]
        fake = FakeAlchemyClient(response_for={"to": incoming, "from": []})
        result = _run(self.svc(fake, repo), fake, VALID_ADDRESS)

        assert result.pagination.source == "provider"
        assert repo.transaction_count() == 2
        assert result.pagination.total == 2

    def test_block_timestamp_backfilled_from_chain_block(self):
        # A provider row WITHOUT metadata.blockTimestamp gets its timestamp
        # resolved from the chain block (eth_getBlockByNumber) and the value is
        # a real timezone-aware datetime, not a raw epoch int.
        svc = BlockchainService(
            pagination=PaginationConfig(max_pages=20, max_transfers=1000),
            wallet_repository=None,
        )
        raw = make_eth("0xchaintime", VALID_LOWER, direction="in", block="0x40")
        raw["metadata"] = {}  # no provider timestamp
        fake = FakeAlchemyClient(
            response_for={"to": [raw], "from": []},
            block_timestamps={0x40: 1700000000},
        )
        result = _run(svc, fake, VALID_ADDRESS)

        assert len(result.transfers) == 1
        t = result.transfers[0]
        assert t.block_number == 0x40
        assert t.block_timestamp is not None
        assert t.block_timestamp.tzinfo is not None
        # datetime.fromtimestamp(1700000000, tz=utc) == 2023-11-14T22:13:20Z
        assert t.block_timestamp.isoformat() == "2023-11-14T22:13:20+00:00"
        assert fake.block_timestamp_calls == [0x40]

    @staticmethod
    def make_rows_blank():
        from wallets.repository import MemoryWalletRepository

        return MemoryWalletRepository()


# --------------------------------------------------------------------------- #
# Pagination (client level)
# --------------------------------------------------------------------------- #
class TestPagination:
    """Verify Alchemy pagination logic without any real HTTP/network use.

    The client's ``_rpc`` transport is stubbed out, so no real socket is ever
    opened and no API key / network is required.
    """

    @staticmethod
    def _client_with_rpc(monkeypatch, handler, max_pages=5):
        from blockchain.alchemy_client import AlchemyClient

        async def fake_rpc(self, payload):
            return handler(payload)

        monkeypatch.setattr(AlchemyClient, "_rpc", fake_rpc)
        return AlchemyClient(api_key="test", pagination=PaginationConfig(max_pages=max_pages))

    def test_follows_page_keys(self, monkeypatch):
        import asyncio

        pages = {
            "p1": {"transfers": [make_eth("0x1", VALID_LOWER)], "pageKey": "p2"},
            "p2": {"transfers": [make_eth("0x2", VALID_LOWER)], "pageKey": "p3"},
            "p3": {"transfers": [make_eth("0x3", VALID_LOWER)]},
        }
        seen: list[str] = []

        def handler(payload):
            params = payload["params"][0]
            key = params.get("pageKey", "p1")
            seen.append(key)
            return pages[key]

        client = self._client_with_rpc(monkeypatch, handler)
        transfers = asyncio.run(client.get_transfers(VALID_LOWER, direction="to"))

        assert seen == ["p1", "p2", "p3"]
        assert [t["hash"] for t in transfers] == ["0x1", "0x2", "0x3"]

    def test_max_pages_enforced(self, monkeypatch):
        import asyncio

        def handler(payload):
            return {"transfers": [make_eth("0x1", VALID_LOWER)], "pageKey": "next"}

        client = self._client_with_rpc(monkeypatch, handler, max_pages=3)
        transfers = asyncio.run(client.get_transfers(VALID_LOWER, direction="to"))
        assert len(transfers) == 3


# --------------------------------------------------------------------------- #
# Provider / API error handling
# --------------------------------------------------------------------------- #
class TestErrors:
    def test_api_error(self, service):
        fake = FakeAlchemyClient(error=AlchemyAPIError("boom"))
        with pytest.raises(AlchemyAPIError):
            _run(service, fake, VALID_ADDRESS)

    def test_http_error(self, service):
        fake = FakeAlchemyClient(error=AlchemyHTTPError("boom"))
        with pytest.raises(AlchemyHTTPError):
            _run(service, fake, VALID_ADDRESS)

    def test_config_error(self):
        import os

        os.environ.pop("ALCHEMY_API_KEY", None)
        with pytest.raises(AlchemyConfigError):
            from blockchain.alchemy_client import AlchemyClient

            AlchemyClient(api_key="   ")

    def test_non_json_provider_response_maps_to_api_error(self, monkeypatch):
        # A 200 with an HTML/non-JSON body (e.g. an expired-key error page)
        # must become AlchemyAPIError -> mapped to 502 by the route, never a 500.
        import asyncio

        from blockchain.alchemy_client import AlchemyClient

        class FakeResponse:
            status_code = 200

            @staticmethod
            def json():
                raise ValueError("expected json")

        class FakeTransport:
            @staticmethod
            async def post(url, json):
                return FakeResponse()

            @staticmethod
            async def aclose():
                return None

        monkeypatch.setattr(
            AlchemyClient, "_get_client", lambda self: FakeTransport()
        )
        client = AlchemyClient(api_key="test")
        with pytest.raises(AlchemyAPIError):
            asyncio.run(client._rpc({"jsonrpc": "2.0", "params": []}))


# --------------------------------------------------------------------------- #
# FastAPI endpoints
# --------------------------------------------------------------------------- #
class TestEndpoints:
    def test_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["project"] == "SIH26182-CryptoTrace"

    def test_invalid_address_returns_400(self, client):
        resp = client.get("/api/v1/wallets/0x123/transfers")
        assert resp.status_code == 400

    def test_transfers_returns_200(self, client, monkeypatch):
        from blockchain.service import BlockchainService

        async def fake_get(self, address, limit=None, offset=None, direction=None, refresh=False):
            # Mirror the real service: the address is normalized to lowercase.
            return WalletTransfers(
                wallet_address=address.lower(),
                chain="eth",
                transfers=[],
                pagination=__import__(
                    "blockchain.models", fromlist=["PaginationInfo"]
                ).PaginationInfo(max_transfers=1000, fetched=0, truncated=False),
            )

        monkeypatch.setattr(BlockchainService, "get_wallet_transfers", fake_get)
        resp = client.get(f"/api/v1/wallets/{VALID_ADDRESS}/transfers")
        assert resp.status_code == 200
        body = resp.json()
        assert body["wallet_address"] == VALID_LOWER
        assert body["transfers"] == []

    def test_provider_error_returns_502(self, client, monkeypatch):
        from blockchain.service import BlockchainService

        async def fake_get(self, address, limit=None, offset=None, direction=None, refresh=False):
            raise AlchemyAPIError("provider down")

        monkeypatch.setattr(BlockchainService, "get_wallet_transfers", fake_get)
        resp = client.get(f"/api/v1/wallets/{VALID_ADDRESS}/transfers")
        assert resp.status_code == 502

    def test_pagination_and_direction_params_reach_service(self, client, monkeypatch):
        from blockchain.service import BlockchainService

        captured = {}

        async def fake_get(self, address, limit=None, offset=None, direction=None, refresh=False):
            captured.update(limit=limit, offset=offset, direction=direction)
            return WalletTransfers(
                wallet_address=address.lower(),
                chain="eth",
                transfers=[],
                pagination=__import__(
                    "blockchain.models", fromlist=["PaginationInfo"]
                ).PaginationInfo(max_transfers=1000, fetched=0, truncated=False),
            )

        monkeypatch.setattr(BlockchainService, "get_wallet_transfers", fake_get)
        resp = client.get(
            f"/api/v1/wallets/{VALID_ADDRESS}/transfers",
            params={"limit": 25, "offset": 50, "direction": "out"},
        )
        assert resp.status_code == 200
        assert captured == {"limit": 25, "offset": 50, "direction": "out"}

    def test_unexpected_error_returns_500(self, client, monkeypatch):
        from blockchain.service import BlockchainService

        async def fake_get(self, address, limit=None, offset=None, direction=None, refresh=False):
            raise RuntimeError("boom")

        monkeypatch.setattr(BlockchainService, "get_wallet_transfers", fake_get)
        resp = client.get(f"/api/v1/wallets/{VALID_ADDRESS}/transfers")
        assert resp.status_code == 500
