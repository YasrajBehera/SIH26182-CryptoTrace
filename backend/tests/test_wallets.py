"""Tests for the wallet persistence + summary surface."""

import pytest

from wallets.repository import MemoryWalletRepository
from wallets.service import WalletService

ADDR = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
COUNTERPARTY = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

TRANSFERS = [
    {
        "chain": "eth",
        "tx_hash": "0x1",
        "block_number": 100,
        "block_timestamp": 1704067200,
        "from_address": COUNTERPARTY,
        "to_address": ADDR,
        "value": "1000000000000000000",
        "token_symbol": "ETH",
    },
    {
        "chain": "eth",
        "tx_hash": "0x2",
        "block_number": 101,
        "block_timestamp": 1704067800,
        "from_address": ADDR,
        "to_address": COUNTERPARTY,
        "value": "250000000000000000",
        "token_symbol": "ETH",
    },
    {
        "chain": "eth",
        "tx_hash": "0x3",
        "block_number": 102,
        "block_timestamp": 1704068400,
        "from_address": ADDR,
        "to_address": COUNTERPARTY,
        "value": "50000000000000000",
        "token_symbol": "ETH",
    },
]


class TestWalletService:
    def setup_method(self):
        self.svc = WalletService(repository=MemoryWalletRepository())

    def test_register_analysis_derives_summary(self):
        self.svc.register_analysis(address=ADDR, chain="eth", transfers=TRANSFERS)
        summary = self.svc.summarize(ADDR, "eth")
        assert summary is not None
        assert summary.address == ADDR
        assert summary.transaction_count == 3
        assert summary.source == "memory"
        assert summary.risk == "unknown"
        assert summary.network == "eth"

    def test_summarize_unknown_wallet_is_none(self):
        assert self.svc.summarize(ADDR, "eth") is None

    def test_volumes_split_by_direction(self):
        stored = self.svc.register_analysis(
            address=ADDR, chain="eth", transfers=TRANSFERS
        )
        assert stored["incoming_volume"] == "1000000000000000000"
        assert stored["outgoing_volume"] == "300000000000000000"
        assert stored["transaction_count"] == 3

    def test_dedup_reingest(self):
        self.svc.register_analysis(address=ADDR, chain="eth", transfers=TRANSFERS)
        self.svc.register_analysis(address=ADDR, chain="eth", transfers=TRANSFERS)
        assert self.svc.summarize(ADDR, "eth").transaction_count == 3

    def test_register_with_risk(self):
        self.svc.register_analysis(
            address=ADDR,
            chain="eth",
            transfers=TRANSFERS,
            risk="high",
            risk_score=80,
        )
        summary = self.svc.summarize(ADDR, "eth")
        assert summary.risk == "high"
        assert summary.risk_score == 80

    def test_list_transactions_filtered(self):
        self.svc.register_analysis(address=ADDR, chain="eth", transfers=TRANSFERS)
        rows = self.svc.repository.list_transactions(address=ADDR, chain="eth")
        assert len(rows) == 3


class TestWalletAPI:
    def test_summary_404_for_never_analyzed(self, app_client):
        resp = app_client.get(
            f"/api/v1/wallets/{ADDR}/summary",
            params={"chain": "eth"},
        )
        assert resp.status_code == 404

    def test_summary_200_after_analysis(self, app_client):
        """Persisted transfer data (via case apply-analysis) drives the summary."""
        case = app_client.post(
            "/api/v1/investigations",
            json={"name": "wallet summary case", "primary_wallet": ADDR},
        ).json()
        resp = app_client.post(
            f"/api/v1/investigations/{case['id']}/apply-analysis",
            json={
                "address": ADDR,
                "analysis_id": "attr-wallet-test",
                "data_source": "live",
                "transactions": [
                    {
                        "chain": "eth",
                        "tx_hash": "0xw1",
                        "block_timestamp": 1704067200,
                        "from_address": COUNTERPARTY,
                        "to_address": ADDR,
                        "value": "5000000000000000000",
                    }
                ],
            },
        )
        assert resp.status_code == 200

        summary = app_client.get(
            f"/api/v1/wallets/{ADDR}/summary",
            params={"chain": "eth"},
        )
        assert summary.status_code == 200
        data = summary.json()
        assert data["address"] == ADDR
        assert data["transaction_count"] >= 1

    def test_summary_invalid_address(self, app_client):
        resp = app_client.get("/api/v1/wallets/not-an-address/summary")
        assert resp.status_code == 422