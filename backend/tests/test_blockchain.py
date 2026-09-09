"""Tests for the Member 1 blockchain data layer.

These tests use mocked blockchain clients and never require a real Alchemy
API key.
"""

from __future__ import annotations

from typing import Any, Optional

import pytest
from fastapi.testclient import TestClient

from app.main import app
from blockchain.alchemy_client import (
    AlchemyAPIError,
    AlchemyConfigError,
    AlchemyHTTPError,
)
from blockchain.models import WalletTransfers
from blockchain.pagination import PaginationConfig
from blockchain.service import BlockchainService
from blockchain.validators import InvalidAddressError, is_valid_address, validate_address

client = TestClient(app)

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
    ) -> None:
        self._response_for = response_for or {"from": [], "to": []}
        self._error = error
        self.calls: list[tuple[str, str]] = []

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

    def test_limit_cap(self):
        svc = BlockchainService(pagination=PaginationConfig(max_transfers=1000))
        rows = [make_eth(f"0x{i}", VALID_LOWER) for i in range(5)]
        fake = FakeAlchemyClient(response_for={"to": rows, "from": []})
        result = _run(svc, fake, VALID_ADDRESS, limit=2)
        assert len(result.transfers) == 2
        assert result.pagination.truncated is True

    def test_invalid_address_raises(self, service):
        fake = FakeAlchemyClient()
        with pytest.raises(InvalidAddressError):
            _run(service, fake, "not-an-address")


def _run(
    service: BlockchainService,
    fake: FakeAlchemyClient,
    address: str,
    limit: Optional[int] = None,
) -> WalletTransfers:
    import asyncio

    service._client = fake
    return asyncio.run(service.get_wallet_transfers(address, limit=limit))


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


# --------------------------------------------------------------------------- #
# FastAPI endpoints
# --------------------------------------------------------------------------- #
class TestEndpoints:
    def test_health(self):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_root(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["project"] == "SIH26182-CryptoTrace"

    def test_invalid_address_returns_400(self):
        resp = client.get("/api/v1/wallets/0x123/transfers")
        assert resp.status_code == 400

    def test_transfers_returns_200(self, monkeypatch):
        from blockchain.service import BlockchainService

        async def fake_get(self, address, limit=None):
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

    def test_provider_error_returns_502(self, monkeypatch):
        from blockchain.service import BlockchainService

        async def fake_get(self, address, limit=None):
            raise AlchemyAPIError("provider down")

        monkeypatch.setattr(BlockchainService, "get_wallet_transfers", fake_get)
        resp = client.get(f"/api/v1/wallets/{VALID_ADDRESS}/transfers")
        assert resp.status_code == 502

    def test_unexpected_error_returns_500(self, monkeypatch):
        from blockchain.service import BlockchainService

        async def fake_get(self, address, limit=None):
            raise RuntimeError("boom")

        monkeypatch.setattr(BlockchainService, "get_wallet_transfers", fake_get)
        resp = client.get(f"/api/v1/wallets/{VALID_ADDRESS}/transfers")
        assert resp.status_code == 500
