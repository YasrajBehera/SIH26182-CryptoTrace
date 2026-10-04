"""Multi-chain provider, chain-resolution and live/demo contract tests.

No test may reach a live network endpoint: every provider is either driven with
a stub client or built without credentials, and the assertions are about the
*contract* (status vocabulary, typed errors, provenance labelling) rather than
about any particular vendor's current response.
"""

import asyncio

import pytest

from blockchain.chains import (
    CHAIN_ALIASES,
    UnsupportedChainError,
    is_recognised_but_unavailable,
    normalize_chain,
    resolve_chain,
    unavailable_reason,
    validate_address_for_chain,
    wallet_id,
)
from blockchain.errors import (
    InvalidAddressError,
    LiveDataUnavailableError,
    ProviderNotConfiguredError,
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
from blockchain.registry import get_provider, provider_status, registered_chains

ADDR = "0x854fbac43f70d16b5ac07dd1e79bd9026f94857c"


# --------------------------------------------------------------------------
# Chain resolution
# --------------------------------------------------------------------------


class TestChainResolution:
    def test_canonical_ids_resolve(self):
        assert resolve_chain("eth").id == "eth"
        assert resolve_chain("ronin").id == "ronin"

    @pytest.mark.parametrize(
        "alias", sorted(a for a, c in CHAIN_ALIASES.items() if c in registered_chains())
    )
    def test_alias_of_an_implemented_chain_resolves(self, alias):
        assert resolve_chain(alias).id == normalize_chain(alias)

    @pytest.mark.parametrize(
        "alias", sorted(a for a, c in CHAIN_ALIASES.items() if c not in registered_chains())
    )
    def test_alias_of_a_known_but_unimplemented_chain_raises(self, alias):
        # Recognising a chain is not the same as being able to investigate it;
        # the difference must be explicit rather than a silent default.
        assert is_recognised_but_unavailable(alias)
        with pytest.raises(UnsupportedChainError):
            resolve_chain(alias)

    def test_unimplemented_chain_explains_itself(self):
        assert "provider" in unavailable_reason("bsc").lower()

    def test_case_and_whitespace_are_tolerated(self):
        assert resolve_chain("  RONIN ").id == "ronin"
        assert resolve_chain("Ethereum").id == "eth"

    def test_unknown_chain_raises_rather_than_defaulting(self):
        with pytest.raises(UnsupportedChainError):
            resolve_chain("not-a-chain")

    def test_missing_chain_is_not_inferred(self):
        with pytest.raises(UnsupportedChainError):
            resolve_chain(None)


# --------------------------------------------------------------------------
# Chain-aware wallet identity
# --------------------------------------------------------------------------


class TestWalletIdentity:
    def test_same_address_on_two_chains_is_two_identities(self):
        assert wallet_id("eth", ADDR) != wallet_id("ronin", ADDR)

    def test_identity_is_chain_qualified_and_lowercased(self):
        assert wallet_id("RONIN", ADDR.upper()) == f"ronin:{ADDR}"

    def test_alias_and_canonical_id_agree(self):
        assert wallet_id("ronin-mainnet", ADDR) == wallet_id("ronin", ADDR)


class TestAddressValidation:
    def test_valid_evm_address_is_normalized(self):
        mixed_case = "0x854Fbac43F70D16B5Ac07Dd1E79bD9026f94857C"
        assert validate_address_for_chain(mixed_case, "eth") == ADDR

    @pytest.mark.parametrize("bad", ["0xunknown", "", "not-an-address", "0x123"])
    def test_malformed_address_is_rejected(self, bad):
        with pytest.raises(InvalidAddressError):
            validate_address_for_chain(bad, "eth")

    def test_malformed_address_is_rejected_on_ronin_too(self):
        with pytest.raises(InvalidAddressError):
            validate_address_for_chain("0xunknown", "ronin")


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------


class TestRegistry:
    def test_both_chains_have_providers(self):
        assert set(registered_chains()) == {"eth", "ronin"}

    @pytest.mark.parametrize("chain", ["eth", "ronin"])
    def test_provider_is_returned_without_touching_the_network(self, chain):
        provider = get_provider(chain)
        assert isinstance(provider, BlockchainProvider)
        assert provider.chain_name == chain

    def test_alias_resolves_to_the_same_provider(self):
        assert get_provider("ronin-mainnet").chain_name == "ronin"

    def test_unknown_chain_raises(self):
        with pytest.raises(UnsupportedChainError):
            get_provider("dogecoin")

    def test_status_snapshot_reports_per_chain_transports(self):
        status = provider_status()
        assert set(status) == set(registered_chains())
        for chain, entry in status.items():
            assert entry["status"] in {"CONFIGURED", "NOT_CONFIGURED"}
            assert isinstance(entry["transports"], list), chain


# --------------------------------------------------------------------------
# Provider contract
# --------------------------------------------------------------------------


class StubProvider(BlockchainProvider):
    """Provider that returns a fixed result, for pipeline contract tests."""

    chain_name = "eth"
    provider_name = "stub"

    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    async def get_transfers(self, address, limit=None):
        if self._error is not None:
            raise self._error
        return self._result

    async def is_healthy(self):
        return True


def make_transfer(**overrides) -> BlockchainTransfer:
    base = dict(
        transaction_hash="0x" + "ab" * 32,
        block_number=100,
        block_timestamp=None,
        from_address=ADDR,
        to_address="0x" + "cd" * 20,
        value="1.5",
        asset="RON",
        category="erc20",
        direction="out",
        raw_contract_address=None,
        raw_contract_value=None,
        chain="eth",
    )
    base.update(overrides)
    return BlockchainTransfer(**base)


class TestProviderContract:
    def test_result_requires_a_status_and_source(self):
        with pytest.raises(Exception):
            ProviderResult(
                chain="eth",
                address=ADDR,
                data_source=SOURCE_LIVE,
                status="",
                provider="stub",
                transfers=[],
            )

    def test_provider_declares_its_chain(self):
        assert StubProvider().chain_name == "eth"

    def test_coroutine_is_awaitable(self):
        result = asyncio.run(StubProvider().get_transfers(ADDR))
        assert result is None


# --------------------------------------------------------------------------
# Ethereum provider: configuration and error translation
# --------------------------------------------------------------------------


class TestEthereumProviderConfiguration:
    def test_missing_key_is_not_configured(self, monkeypatch):
        from blockchain.ethereum_provider import EthereumProvider

        monkeypatch.delenv("ALCHEMY_API_KEY", raising=False)
        provider = EthereumProvider()
        assert provider.is_configured() is False
        assert provider.describe_transports() == []
        assert asyncio.run(provider.is_healthy()) is False

    def test_configured_key_enables_the_alchemy_transport(self, monkeypatch):
        from blockchain.ethereum_provider import EthereumProvider

        monkeypatch.setenv("ALCHEMY_API_KEY", "test-key")
        provider = EthereumProvider()
        assert provider.is_configured() is True
        assert provider.describe_transports() == ["alchemy"]

    def test_missing_key_raises_not_configured_rather_than_faking_data(self, monkeypatch):
        from blockchain.ethereum_provider import EthereumProvider

        monkeypatch.delenv("ALCHEMY_API_KEY", raising=False)
        with pytest.raises(ProviderNotConfiguredError) as excinfo:
            asyncio.run(EthereumProvider().get_transfers(ADDR))
        assert excinfo.value.status == "NOT_CONFIGURED"
        assert excinfo.value.http_status == 503

    def test_malformed_address_raises_invalid_address(self, monkeypatch):
        from blockchain.ethereum_provider import EthereumProvider

        monkeypatch.setenv("ALCHEMY_API_KEY", "test-key")
        with pytest.raises(InvalidAddressError):
            asyncio.run(EthereumProvider().get_transfers("0xunknown"))


# --------------------------------------------------------------------------
# Ronin provider: real transports, no invention
# --------------------------------------------------------------------------


class TestRoninLogWindowChunking:
    def test_ranges_never_exceed_the_rpc_limit(self):
        from blockchain.ronin_provider import RPC_MAX_BLOCK_RANGE, _chunk_range

        chunks = _chunk_range(0, 5000)
        assert chunks
        assert all(end - start + 1 <= RPC_MAX_BLOCK_RANGE for start, end in chunks)

    def test_chunks_cover_the_whole_window_without_gaps(self):
        from blockchain.ronin_provider import _chunk_range

        chunks = _chunk_range(1000, 2500)
        covered = set()
        for start, end in chunks:
            covered.update(range(start, end + 1))
        assert covered == set(range(1000, 2501))

    def test_empty_window_yields_no_requests(self):
        from blockchain.ronin_provider import _chunk_range

        assert _chunk_range(10, 5) == []


class TestRoninValueDecoding:
    def test_erc20_amount(self):
        from blockchain.ronin_provider import _decode_log_value

        # 1000 * 10**18
        data = "0x" + format(1000 * 10**18, "064x")
        assert _decode_log_value("erc20", data) == 1000 * 10**18

    def test_erc20_humanized_with_contract_decimals(self):
        from blockchain.ronin_provider import _decode_log_value, _humanize

        raw = _decode_log_value("erc20", "0x" + format(3 * 10**18, "064x"))
        assert _humanize(raw, 18) == "3"

    def test_uint256_decimals_response_decodes_as_uint(self):
        from blockchain.ronin_provider import _int

        # What eth_call("decimals()") returns for an 18-decimals token.
        assert _int("0x" + "0" * 63 + "12") == 18

    def test_erc1155_single_uses_the_value_word(self):
        from blockchain.ronin_provider import _decode_log_value

        token_id = format(7, "064x")
        amount = format(5, "064x")
        assert _decode_log_value("erc1155_single", "0x" + token_id + amount) == 5


class TestRoninProviderBehaviour:
    def test_disabling_rpc_and_alchemy_is_not_configured(self, monkeypatch):
        from blockchain.ronin_provider import RoninProvider

        monkeypatch.delenv("RONIN_ALCHEMY_API_KEY", raising=False)
        monkeypatch.setenv("RONIN_RPC_ENABLED", "false")
        provider = RoninProvider()
        assert provider.describe_transports() == []
        with pytest.raises(ProviderNotConfiguredError):
            asyncio.run(provider.get_transfers(ADDR))

    def test_failure_never_becomes_synthetic_transfers(self, monkeypatch):
        from blockchain.ronin_provider import RoninProvider

        monkeypatch.delenv("RONIN_ALCHEMY_API_KEY", raising=False)
        monkeypatch.setenv("RONIN_RPC_ENABLED", "true")
        provider = RoninProvider()
        provider._rpc = object()  # any attribute access fails
        with pytest.raises(LiveDataUnavailableError):
            asyncio.run(provider.get_transfers(ADDR))

    def test_malformed_address_is_rejected_before_any_request(self, monkeypatch):
        from blockchain.ronin_provider import RoninProvider

        monkeypatch.setenv("RONIN_RPC_ENABLED", "true")
        with pytest.raises(InvalidAddressError):
            asyncio.run(RoninProvider().get_transfers("0xunknown"))

    def test_chain_id_is_ronin_not_ethereum(self):
        from blockchain.ronin_provider import CHAIN_ID, DEFAULT_EVM_CHAIN_ID

        assert CHAIN_ID == "ronin"
        # Ronin's EVM chain id is 2020; it must never be inferred from the 0x prefix.
        assert DEFAULT_EVM_CHAIN_ID == "2020"


# --------------------------------------------------------------------------
# Status vocabulary
# --------------------------------------------------------------------------


class TestRoninNativeTransfers:
    """Native RON emits no log, so it is found by reading block transactions.

    That makes it easy to double-count token transfers as RON, which the guards
    below exist to prevent.
    """

    WALLET = "0x854fbac43f70d16b5ac07dd1e79bd9026f94857c"

    def _provider(self, monkeypatch, transactions, head=1_000, window=1):
        from blockchain.ronin_provider import RoninProvider

        provider = RoninProvider()

        class _Rpc:
            def __init__(self):
                self.fetched = []

            async def block_with_transactions(self, block_number):
                self.fetched.append(block_number)
                if block_number != head:
                    return None
                return {
                    "number": hex(head),
                    "timestamp": hex(1_700_000_000),
                    "transactions": transactions,
                }

        provider._rpc = _Rpc()
        monkeypatch.setenv("RONIN_NATIVE_SCAN_BLOCKS", str(window))
        return provider

    def test_value_transfer_is_captured(self, monkeypatch):
        provider = self._provider(
            monkeypatch,
            [
                {
                    "hash": "0xfeed",
                    "from": self.WALLET,
                    "to": "0x" + "11" * 20,
                    "value": hex(3 * 10**18),
                }
            ],
        )
        transfers, scanned_to = asyncio.run(
            provider._native_transfers(self.WALLET, 1_000, budget=1)
        )
        assert len(transfers) == 1
        found = transfers[0]
        assert found.asset == "RON"
        assert found.value == "3"
        assert found.direction == "out"
        assert found.category == "native"
        assert found.transaction_hash == "0xfeed"
        assert found.chain == "ronin"
        assert scanned_to == 1_000

    def test_incoming_value_transfer_is_marked_in(self, monkeypatch):
        provider = self._provider(
            monkeypatch,
            [
                {
                    "hash": "0xbeef",
                    "from": "0x" + "22" * 20,
                    "to": self.WALLET,
                    "value": hex(1 * 10**18),
                }
            ],
        )
        transfers, _ = asyncio.run(
            provider._native_transfers(self.WALLET, 1_000, budget=1)
        )
        assert transfers[0].direction == "in"

    def test_zero_value_contract_call_is_not_a_native_transfer(self, monkeypatch):
        """An ERC-20 ``transfer()`` call carries value 0; counting it as RON
        would report the same movement twice under two different assets."""
        provider = self._provider(
            monkeypatch,
            [
                {
                    "hash": "0xtokencall",
                    "from": self.WALLET,
                    "to": "0xtokencontract",
                    "value": hex(0),
                }
            ],
        )
        transfers, _ = asyncio.run(
            provider._native_transfers(self.WALLET, 1_000, budget=1)
        )
        assert transfers == []

    def test_contract_creation_moves_no_ron(self, monkeypatch):
        provider = self._provider(
            monkeypatch,
            [{"hash": "0xcreate", "from": self.WALLET, "to": None, "value": hex(5)}],
        )
        transfers, _ = asyncio.run(
            provider._native_transfers(self.WALLET, 1_000, budget=1)
        )
        assert transfers == []

    def test_burn_to_zero_address_is_not_a_transfer(self, monkeypatch):
        provider = self._provider(
            monkeypatch,
            [
                {
                    "hash": "0xburn",
                    "from": self.WALLET,
                    "to": "0x" + "0" * 40,
                    "value": hex(9 * 10**18),
                }
            ],
        )
        transfers, _ = asyncio.run(
            provider._native_transfers(self.WALLET, 1_000, budget=1)
        )
        assert transfers == []

    def test_transaction_without_hash_is_skipped_not_invented(self, monkeypatch):
        provider = self._provider(
            monkeypatch,
            [{"from": self.WALLET, "to": "0x" + "11" * 20, "value": hex(1)}],
        )
        transfers, _ = asyncio.run(
            provider._native_transfers(self.WALLET, 1_000, budget=1)
        )
        assert transfers == []

    def test_budget_bounds_the_number_of_blocks_read(self, monkeypatch):
        provider = self._provider(monkeypatch, [], head=1_000, window=50)
        asyncio.run(provider._native_transfers(self.WALLET, 1_000, budget=3))
        assert len(provider._rpc.fetched) == 3

    def test_window_bounds_the_number_of_blocks_read(self, monkeypatch):
        provider = self._provider(monkeypatch, [], head=1_000, window=5)
        asyncio.run(provider._native_transfers(self.WALLET, 1_000, budget=1_000))
        assert len(provider._rpc.fetched) == 5


class TestStatusVocabulary:
    def test_partial_live_is_distinct_from_full_live(self):
        assert STATUS_LIVE != STATUS_LIVE_PARTIAL
        assert STATUS_LIVE_PARTIAL != "DEMO"

    def test_no_data_is_a_success_status_not_an_error(self):
        assert STATUS_NO_DATA == "NO_DATA"


# --------------------------------------------------------------------------
# Ronin discovery: filters, pagination and honesty about empty results
# --------------------------------------------------------------------------


class TestRoninDiscoveryFilters:
    """The wallet must be matched in BOTH topic positions of a Transfer event.

    ``Transfer(from, to, value)`` encodes the sender in ``topic1`` and the
    recipient in ``topic2``. A single ``[topic0, wallet]`` filter therefore only
    ever finds *outgoing* transfers and silently drops every incoming one.
    """

    def test_filters_cover_outgoing_and_incoming_positions(self):
        from blockchain.ronin_provider import LOG_FILTERS

        specs = [spec("0x" + "11" * 32) for _label, spec in LOG_FILTERS]
        # Some filter must pin the wallet to topic1 (outgoing) ...
        assert any(len(spec) == 2 and spec[1] is not None for spec in specs)
        # ... and some filter must pin it to topic2 (incoming).
        assert any(
            len(spec) == 3 and spec[2] is not None for spec in specs
        )

    def test_filter_topics_are_event_hashes_not_category_names(self):
        """A filter built from ``TRANSFER_TOPICS`` *values* is syntactically valid
        and matches nothing, which is indistinguishable from an inactive wallet.

        This regressed once: ``["erc20", "erc721", ...]`` as topic0 silently
        returned zero rows for wallets that demonstrably transacted, so the
        provider reported NO_DATA for a very active Ronin wallet.
        """
        from blockchain.ronin_provider import LOG_FILTERS, TRANSFER_TOPICS

        known = {topic.lower() for topic in TRANSFER_TOPICS}
        wallet = "0x" + "11" * 32
        for _label, spec in LOG_FILTERS:
            topic0 = spec(wallet)[0]
            entries = topic0 if isinstance(topic0, list) else [topic0]
            for entry in entries:
                assert entry.lower() in known, (
                    f"{entry!r} is not a Transfer event hash; filters must carry "
                    "topic0 hashes, never category names"
                )

    def test_every_supported_standard_is_reachable_by_some_filter(self):
        from blockchain.ronin_provider import LOG_FILTERS, TRANSFER_TOPICS

        wallet = "0x" + "11" * 32
        reachable = set()
        for _label, spec in LOG_FILTERS:
            topic0 = spec(wallet)[0]
            entries = topic0 if isinstance(topic0, list) else [topic0]
            reachable.update(entry.lower() for entry in entries)
        assert reachable == {topic.lower() for topic in TRANSFER_TOPICS}

    def test_incoming_filter_leaves_topic1_unconstrained(self):
        from blockchain.ronin_provider import LOG_FILTERS

        wallet = "0x" + "11" * 32
        built = [spec(wallet) for _label, spec in LOG_FILTERS]
        incoming = [spec for spec in built if len(spec) == 3 and spec[2] == wallet]
        assert incoming, "no filter matches the wallet in the recipient slot"
        for spec in incoming:
            assert spec[1] is None, "incoming filter must not pin the sender slot"

    def test_topic0_uses_the_or_array_form_to_batch_event_signatures(self):
        """The OR-array form is used deliberately to cut request count.

        The public endpoint accepts both a scalar topic0 and an OR-array. We use
        the array so all three event signatures (20/721/1155) are covered by a
        single request per direction, which matters because the endpoint
        throttles aggressively. Regression guard for the original defect: topic0
        must be the real event-signature *hashes*, never the category labels.
        """
        from blockchain.ronin_provider import LOG_FILTERS, TRANSFER_TOPICS

        known = {str(t).lower() for t in TRANSFER_TOPICS}
        wallet = "0x" + "11" * 32
        for _label, spec in LOG_FILTERS:
            topic0 = spec(wallet)[0]
            assert isinstance(topic0, list), "topic0 must be an OR-array"
            assert topic0, "topic0 must not be empty"
            for entry in topic0:
                assert isinstance(entry, str) and entry.startswith("0x"), (
                    f"topic0 entries must be hashes, got {entry!r}"
                )
                assert len(entry) == 66, (
                    f"topic0 entries must be 32-byte hashes, got {entry!r}"
                )
                assert entry.lower() in known, (
                    f"topic0 must be a known transfer signature, got {entry!r}"
                )

    def test_erc1155_batch_outgoing_is_not_dropped(self):
        """ERC-1155 batch puts the operator in topic1 and recipient in topic2."""
        from blockchain.ronin_provider import LOG_FILTERS

        wallet = "0x" + "11" * 32
        built = [spec(wallet) for _label, spec in LOG_FILTERS]
        batch = [
            spec
            for spec in built
            if len(spec) == 3 and spec[1] == wallet and spec[2] is None
        ]
        assert batch, "outgoing ERC-1155 batch transfers would be missed"


class TestRoninNewestFirstPagination:
    def test_chunks_are_ordered_newest_first(self):
        from blockchain.ronin_provider import _chunk_range, _chunk_range_newest_first

        chunks = _chunk_range(1000, 5000)
        assert _chunk_range_newest_first(1000, 5000) == list(reversed(chunks))

    def test_newest_first_still_respects_the_rpc_block_limit(self):
        from blockchain.ronin_provider import (
            RPC_MAX_BLOCK_RANGE,
            _chunk_range_newest_first,
        )

        assert all(
            end - start + 1 <= RPC_MAX_BLOCK_RANGE
            for start, end in _chunk_range_newest_first(0, 100_000)
        )

    def test_scan_window_is_not_capped_at_200_blocks(self):
        """The 200-block ceiling silently hid any activity older than minutes."""
        from blockchain.ronin_provider import DEFAULT_SCAN_BLOCKS, MAX_SCAN_BLOCKS

        assert DEFAULT_SCAN_BLOCKS > 200
        assert MAX_SCAN_BLOCKS > 200

    def test_configured_window_is_honoured(self, monkeypatch):
        from blockchain.ronin_provider import RoninProvider

        monkeypatch.setenv("RONIN_SCAN_BLOCKS", "5000")
        assert RoninProvider()._scan_window() == 5000

    def test_absurd_window_is_clamped_not_trusted(self, monkeypatch):
        from blockchain.ronin_provider import MAX_SCAN_BLOCKS, RoninProvider

        monkeypatch.setenv("RONIN_SCAN_BLOCKS", str(MAX_SCAN_BLOCKS + 10**9))
        assert RoninProvider()._scan_window() == MAX_SCAN_BLOCKS

    def test_request_budget_defaults_to_a_bounded_value(self, monkeypatch):
        from blockchain.ronin_provider import DEFAULT_MAX_REQUESTS, RoninProvider

        monkeypatch.delenv("RONIN_MAX_REQUESTS", raising=False)
        assert RoninProvider()._request_budget() == DEFAULT_MAX_REQUESTS

    def test_nonzero_budget_survives_a_nonsense_value(self, monkeypatch):
        from blockchain.ronin_provider import RoninProvider

        monkeypatch.setenv("RONIN_MAX_REQUESTS", "not-a-number")
        assert RoninProvider()._request_budget() > 0


class TestRoninFilterSelfCheck:
    """The endpoint returns EMPTY (not an error) when throttling.

    Without a self-check a throttled scan is indistinguishable from an inactive
    wallet, which is exactly how a false ``NO_DATA`` gets reported.
    """

    def _provider_with(self, monkeypatch, control, probe):
        from blockchain.ronin_provider import RoninProvider

        provider = RoninProvider()
        client = _StubRpcClient(control=control, probe=probe)
        provider._rpc = client
        return provider

    def test_filters_proven_functional_when_probe_matches(self, monkeypatch):
        from blockchain.ronin_provider import TRANSFER_TOPICS

        topic0 = next(iter(TRANSFER_TOPICS))
        probe_topic = "0x" + "00" * 12 + "22" * 20
        provider = self._provider_with(
            monkeypatch,
            control=[{"topics": [topic0, probe_topic, probe_topic]}],
            probe=[{"transactionHash": "0xabc"}],
        )
        assert asyncio.run(provider._filters_are_functional([(100, 200)])) is True

    def test_throttling_is_detected_when_even_the_unfiltered_query_is_empty(self, monkeypatch):
        from blockchain.ronin_provider import RoninProvider

        provider = self._provider_with(monkeypatch, control=[], probe=[])
        assert asyncio.run(provider._filters_are_functional([(100, 200)])) is False

    def test_broken_filters_are_detected_by_the_probe(self, monkeypatch):
        from blockchain.ronin_provider import TRANSFER_TOPICS

        topic0 = next(iter(TRANSFER_TOPICS))
        probe_topic = "0x" + "00" * 12 + "22" * 20
        provider = self._provider_with(
            monkeypatch,
            control=[{"topics": [topic0, probe_topic, probe_topic]}],
            probe=[],
        )
        assert asyncio.run(provider._filters_are_functional([(100, 200)])) is False

    def test_no_chunks_means_nothing_can_be_validated(self, monkeypatch):
        from blockchain.ronin_provider import RoninProvider

        provider = self._provider_with(monkeypatch, control=[], probe=[])
        assert asyncio.run(provider._filters_are_functional([])) is False


class _StubRpcClient:
    """Minimal stand-in for :class:`RoninRpcClient` used by the self-check tests."""

    def __init__(self, control, probe):
        self._control = control
        self._probe = probe
        self.requests = []

    async def get_logs(self, params):
        self.requests.append(params)
        topics = params.get("topics") or []
        # An unfiltered control query carries every topic0 and no address.
        if len(topics) == 1 and isinstance(topics[0], list) and len(topics[0]) > 1:
            return self._control
        return self._probe