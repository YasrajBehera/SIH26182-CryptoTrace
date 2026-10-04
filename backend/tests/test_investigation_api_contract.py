"""HTTP contract for POST /api/v1/investigations/{address}/analyze.

Asserts the honesty rules at the boundary the UI actually consumes: a strict live
request that cannot obtain real data must fail with an accurate status instead of
returning a 200 made of synthetic transactions.
"""

import pytest

import pipeline.api as pipeline_api
from blockchain.errors import (
    InvalidAddressError,
    LiveDataUnavailableError,
    ProviderNotConfiguredError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    UnsupportedChainError,
)


def stub_pipeline(monkeypatch, *, result=None, error=None):
    """Replace the module-level pipeline with one driven by a stub provider."""
    from blockchain.models import BlockchainTransfer
    from blockchain.providers import (
        SOURCE_LIVE,
        STATUS_LIVE,
        BlockchainProvider,
        ProviderResult,
    )
    from pipeline.service import InvestigationPipeline

    def make_transfer():
        return BlockchainTransfer(
            transaction_hash="0x" + "ab" * 32,
            block_number=1000,
            block_timestamp=None,
            from_address="0x854fbac43f70d16b5ac07dd1e79bd9026f94857c",
            to_address="0x" + "cd" * 20,
            value="1.0",
            asset="RON",
            category="erc20",
            direction="out",
            raw_contract_address=None,
            raw_contract_value=None,
            chain="ronin",
        )

    class StubProvider(BlockchainProvider):
        chain_name = "ronin"
        provider_name = "stub"

        async def get_transfers(self, address, limit=None):
            if error is not None:
                raise error
            return result or ProviderResult(
                chain="ronin",
                address=address,
                data_source=SOURCE_LIVE,
                status=STATUS_LIVE,
                provider="stub",
                transfers=[make_transfer()],
            )

    pipeline = InvestigationPipeline(
        sync_to_neo4j=False, provider_factory=lambda chain: StubProvider()
    )
    monkeypatch.setattr(pipeline_api, "_pipeline", pipeline)
    return pipeline


URL = "/api/v1/investigations/0x854fbac43f70d16b5ac07dd1e79bd9026f94857c/analyze"


class TestStrictLiveModeOverHttp:
    @pytest.mark.parametrize(
        "error,expected_status",
        [
            (LiveDataUnavailableError("upstream 500", chain="ronin"), "LIVE_DATA_UNAVAILABLE"),
            (ProviderNotConfiguredError("ronin", "no credentials"), "NOT_CONFIGURED"),
            (ProviderTimeoutError("timed out", chain="ronin"), "PROVIDER_TIMEOUT"),
            (ProviderRateLimitError("slow down", chain="ronin"), "PROVIDER_RATE_LIMITED"),
            (ProviderResponseError("bad payload", chain="ronin"), "PROVIDER_ERROR"),
        ],
    )
    def test_failure_is_reported_with_its_own_status(self, app_client, monkeypatch, error, expected_status):
        stub_pipeline(monkeypatch, error=error)
        resp = app_client.post(URL, params={"chain": "ronin", "mode": "live"})
        assert resp.status_code != 200
        assert resp.json()["detail"]["status"] == expected_status
        assert resp.json()["detail"]["data_source"] == "unavailable"

    def test_rate_limit_surfaces_as_429_not_generic_503(self, app_client, monkeypatch):
        stub_pipeline(monkeypatch, error=ProviderRateLimitError("slow down", chain="ronin"))
        resp = app_client.post(URL, params={"chain": "ronin", "mode": "live"})
        assert resp.status_code == 429

    def test_timeout_surfaces_as_504(self, app_client, monkeypatch):
        stub_pipeline(monkeypatch, error=ProviderTimeoutError("timed out", chain="ronin"))
        resp = app_client.post(URL, params={"chain": "ronin", "mode": "live"})
        assert resp.status_code == 504

    def test_misconfigured_provider_surfaces_as_503(self, app_client, monkeypatch):
        stub_pipeline(monkeypatch, error=ProviderNotConfiguredError("ronin", "no credentials"))
        resp = app_client.post(URL, params={"chain": "ronin", "mode": "live"})
        assert resp.status_code == 503

    def test_error_response_never_contains_transactions(self, app_client, monkeypatch):
        stub_pipeline(monkeypatch, error=LiveDataUnavailableError("down", chain="ronin"))
        resp = app_client.post(URL, params={"chain": "ronin", "mode": "live"})
        body = resp.json()
        assert "transactions" not in body.get("detail", {})
        assert "candidates" not in body.get("detail", {})


class TestInputValidationOverHttp:
    def test_malformed_address_is_rejected(self, app_client):
        resp = app_client.post(
            "/api/v1/investigations/0xunknown/analyze", params={"chain": "eth"}
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["status"] == "INVALID_ADDRESS"

    def test_unknown_chain_is_rejected(self, app_client):
        resp = app_client.post(URL, params={"chain": "not-a-chain"})
        assert resp.status_code == 400
        assert resp.json()["detail"]["status"] == "UNSUPPORTED_CHAIN"

    def test_unimplemented_chain_is_rejected_rather_than_guessed(self, app_client):
        resp = app_client.post(URL, params={"chain": "bsc"})
        assert resp.status_code == 400
        assert resp.json()["detail"]["status"] == "UNSUPPORTED_CHAIN"

    def test_invalid_mode_is_rejected_by_validation(self, app_client):
        resp = app_client.post(URL, params={"chain": "ronin", "mode": "sneaky"})
        assert resp.status_code == 422


class TestDemoModeOverHttp:
    def test_demo_mode_returns_labelled_synthetic_data(self, app_client, monkeypatch):
        stub_pipeline(monkeypatch)
        resp = app_client.post(URL, params={"chain": "ronin", "mode": "demo"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["data_source"] == "demo"
        assert data["status"] == "DEMO"
        assert data["provider"] == "synthetic"

    def test_demo_mode_does_not_call_the_provider(self, app_client, monkeypatch):
        stub_pipeline(monkeypatch)
        resp = app_client.post(URL, params={"chain": "ronin", "mode": "demo"})
        assert resp.json()["provider"] == "synthetic"


class TestLiveSuccessOverHttp:
    def test_live_success_reports_provenance(self, app_client, monkeypatch):
        stub_pipeline(monkeypatch)
        resp = app_client.post(URL, params={"chain": "ronin", "mode": "live"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["data_source"] == "live"
        assert data["status"] == "LIVE"
        assert data["chain"] == "ronin"
        assert data["live_status"] == "LIVE"
        assert data["transfers_ingested"] >= 1


class TestChainDiscovery:
    def test_chains_endpoint_lists_supported_chains(self, app_client):
        resp = app_client.get("/api/v1/investigations/chains")
        assert resp.status_code == 200
        body = resp.json()
        assert "eth" in body["chains"]
        assert "ronin" in body["chains"]
        assert body["aliases"]["ronin-mainnet"] == "ronin"