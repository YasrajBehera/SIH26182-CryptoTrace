"""Live/demo provenance contract for the investigation pipeline.

These tests pin the rule the whole project depends on: a live investigation that
cannot obtain real chain data must never be reported as a successful analysis
made of synthetic transactions. Every case is driven through a stub provider, so
nothing here touches a network endpoint.
"""

import pytest

from blockchain.errors import (
    InvalidAddressError,
    LiveDataUnavailableError,
    ProviderNotConfiguredError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    UnsupportedChainError,
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
from pipeline.models import InvestigationRequest
from pipeline.service import MODE_AUTO, MODE_DEMO, MODE_LIVE, InvestigationPipeline

ADDR = "0x854fbac43f70d16b5ac07dd1e79bd9026f94857c"


def make_transfer(**overrides) -> BlockchainTransfer:
    base = dict(
        transaction_hash="0x" + "ab" * 32,
        block_number=1000,
        block_timestamp=None,
        from_address=ADDR,
        to_address="0x" + "cd" * 20,
        value="2.5",
        asset="RON",
        category="erc20",
        direction="out",
        raw_contract_address=None,
        raw_contract_value=None,
        chain="ronin",
    )
    base.update(overrides)
    return BlockchainTransfer(**base)


class StubProvider(BlockchainProvider):
    """Returns a preset result, or raises a preset error."""

    def __init__(self, chain="ronin", result=None, error=None):
        self.chain_name = chain
        self.provider_name = "stub"
        self._result = result
        self._error = error
        self.calls = 0

    async def get_transfers(self, address, limit=None):
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._result


def live_result(transfers, status=STATUS_LIVE, chain="ronin", limitations=None):
    return ProviderResult(
        chain=chain,
        address=ADDR,
        data_source=SOURCE_LIVE,
        status=status,
        provider="stub",
        transfers=list(transfers),
        limitations=list(limitations or []),
    )


def pipeline_for(provider, **kwargs) -> InvestigationPipeline:
    return InvestigationPipeline(
        sync_to_neo4j=False,
        provider_factory=lambda chain: provider,
        **kwargs,
    )


def request_for(**overrides) -> InvestigationRequest:
    base = dict(address=ADDR, chain="ronin")
    base.update(overrides)
    return InvestigationRequest(**base)


# --------------------------------------------------------------------------
# Strict mode: a failed live request is an honest failure
# --------------------------------------------------------------------------


class TestLiveModeNeverFallsBack:
    @pytest.mark.parametrize(
        "error",
        [
            LiveDataUnavailableError("upstream 500", chain="ronin"),
            ProviderNotConfiguredError("ronin", "no credentials"),
            ProviderTimeoutError("timed out", chain="ronin"),
            ProviderRateLimitError("rate limited", chain="ronin"),
        ],
    )
    def test_provider_failure_raises_instead_of_returning_demo_data(self, error):
        pipeline = pipeline_for(StubProvider(error=error))
        with pytest.raises(type(error)):
            pipeline.run(request_for(), mode=MODE_LIVE)

    def test_no_synthetic_transactions_leak_into_a_failed_live_run(self):
        """A failed live run must not have ingested anything at all."""
        pipeline = pipeline_for(
            StubProvider(error=LiveDataUnavailableError("down", chain="ronin"))
        )
        with pytest.raises(LiveDataUnavailableError):
            pipeline.run(request_for(), mode=MODE_LIVE)
        # The provider was asked exactly once; no fallback fetch was attempted.
        assert pipeline._provider_factory("ronin").calls == 1

    def test_unsupported_chain_is_an_explicit_error_not_an_eth_guess(self):
        pipeline = pipeline_for(StubProvider(chain="eth"))
        with pytest.raises(UnsupportedChainError):
            pipeline.run(request_for(chain="bsc"), mode=MODE_LIVE)

    def test_malformed_address_is_an_explicit_error(self):
        pipeline = pipeline_for(StubProvider())
        with pytest.raises(InvalidAddressError):
            pipeline.run(request_for(address="0xunknown"), mode=MODE_LIVE)


# --------------------------------------------------------------------------
# Live mode: honest success paths
# --------------------------------------------------------------------------


class TestLiveModeSuccess:
    def test_real_transfers_produce_a_live_result(self):
        provider = StubProvider(result=live_result([make_transfer()]))
        result = pipeline_for(provider).run(request_for(), mode=MODE_LIVE)
        assert result.data_source == "live"
        assert result.status == STATUS_LIVE
        assert result.transfers_ingested == 1
        assert result.graph_edges >= 1

    def test_partial_live_status_is_preserved_and_labelled(self):
        provider = StubProvider(
            result=live_result(
                [make_transfer()],
                status=STATUS_LIVE_PARTIAL,
                limitations=["Native RON transfers are not indexed."],
            )
        )
        result = pipeline_for(provider).run(request_for(), mode=MODE_LIVE)
        assert result.status == STATUS_LIVE_PARTIAL
        assert result.data_source == "live"
        assert any("not indexed" in text for text in result.limitations)

    def test_no_activity_is_reported_as_no_data_not_as_failure(self):
        provider = StubProvider(result=live_result([], status=STATUS_NO_DATA))
        result = pipeline_for(provider).run(request_for(), mode=MODE_LIVE)
        assert result.data_source == "live"
        assert result.status == STATUS_NO_DATA
        assert result.transfers_ingested == 0

    def test_unknown_chain_is_never_inferred_from_the_address(self):
        """Same address on two chains must not share one identity."""
        pipeline = pipeline_for(StubProvider(result=live_result([make_transfer()])))
        result = pipeline.run(request_for(), mode=MODE_LIVE)
        assert result.chain == "ronin"
        assert result.address == ADDR


# --------------------------------------------------------------------------
# Demo mode: synthetic data only, always labelled
# --------------------------------------------------------------------------


class TestDemoMode:
    def test_demo_mode_never_calls_a_provider(self):
        provider = StubProvider(result=live_result([make_transfer()]))
        result = pipeline_for(provider).run(request_for(), mode=MODE_DEMO)
        assert provider.calls == 0
        assert result.data_source == "demo"
        assert result.status == "DEMO"
        assert result.provider == "synthetic"
        assert "NOT real chain activity" in " ".join(result.limitations) or "synthetic" in result.message

    def test_explicit_synthetic_transfers_are_honoured(self):
        pipeline = pipeline_for(StubProvider())
        result = pipeline.run(request_for(), synth_txs=[make_transfer()], mode=MODE_AUTO)
        assert result.data_source == "demo"
        assert result.transfers_ingested == 1

    def test_demo_mode_is_marked_synthetic_in_the_message(self):
        pipeline = pipeline_for(StubProvider())
        result = pipeline.run(request_for(), mode=MODE_DEMO)
        assert "synthetic" in result.message.lower()
        assert result.live_status == ""


# --------------------------------------------------------------------------
# Auto mode: labelled fallback, never silent
# --------------------------------------------------------------------------


class TestAutoMode:
    def test_live_data_wins_when_available(self):
        provider = StubProvider(result=live_result([make_transfer()]))
        result = pipeline_for(provider).run(request_for(), mode=MODE_AUTO)
        assert result.data_source == "live"
        assert result.status == STATUS_LIVE

    def test_failure_falls_back_to_demo_but_says_so_loudly(self):
        provider = StubProvider(
            error=LiveDataUnavailableError("official RPC unreachable", chain="ronin")
        )
        result = pipeline_for(provider).run(request_for(), mode=MODE_AUTO)
        assert result.data_source == "demo"
        assert result.status == "DEMO"
        assert result.provider == "synthetic"
        # The live failure must remain visible to the caller and the UI.
        assert result.live_status == "LIVE_DATA_UNAVAILABLE"
        joined = " ".join(result.limitations)
        assert "LIVE" in joined
        assert "NOT real chain activity" in joined
        assert "official RPC unreachable" in joined

    def test_no_live_activity_falls_back_but_records_no_data(self):
        provider = StubProvider(result=live_result([], status=STATUS_NO_DATA))
        result = pipeline_for(provider).run(request_for(), mode=MODE_AUTO)
        assert result.data_source == "demo"
        assert result.live_status == STATUS_NO_DATA

    def test_fallback_is_never_silently_labelled_as_live(self):
        provider = StubProvider(error=LiveDataUnavailableError("down", chain="ronin"))
        result = pipeline_for(provider).run(request_for(), mode=MODE_AUTO)
        assert result.data_source != "live"
        assert result.status != STATUS_LIVE


# --------------------------------------------------------------------------
# Durable stores must only ever receive real data
# --------------------------------------------------------------------------


class TestDurableStoreOnlyReceivesLiveData:
    def test_demo_fallback_does_not_persist_synthetic_rows(self):
        provider = StubProvider(error=LiveDataUnavailableError("down", chain="ronin"))
        pipeline = pipeline_for(provider)
        registered = []
        pipeline.wallets_service.register_analysis = lambda **kw: registered.append(kw)
        pipeline.run(request_for(), mode=MODE_AUTO)
        assert registered == []

    def test_real_transfers_are_persisted(self):
        provider = StubProvider(result=live_result([make_transfer()]))
        pipeline = pipeline_for(provider)
        registered = []
        pipeline.wallets_service.register_analysis = lambda **kw: registered.append(kw)
        pipeline.run(request_for(), mode=MODE_LIVE)
        assert len(registered) == 1
        assert registered[0]["chain"] == "ronin"
        assert registered[0]["transfers"][0]["chain"] == "ronin"


# --------------------------------------------------------------------------
# Mode validation
# --------------------------------------------------------------------------


class TestModeValidation:
    def test_unknown_mode_is_rejected(self):
        pipeline = pipeline_for(StubProvider())
        with pytest.raises(ValueError):
            pipeline.run(request_for(), mode="sneaky")

    def test_supported_chains_are_discoverable(self):
        assert set(InvestigationPipeline.supported_chains()) == {"eth", "ronin"}