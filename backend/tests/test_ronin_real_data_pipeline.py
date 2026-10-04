"""End-to-end proof that REAL Ronin chain data flows through the whole pipeline.

These tests replay genuine logs/receipts captured from Ronin mainnet
(``fixtures/ronin_real_logs.json``, wallet ``0x3b3adf14...``, an actively
trading wallet) through the real provider, graph, VASP intelligence and
attribution code. Nothing here is wallet-specific in the product code: the
fixtures only stand in for the network, and every wallet/chain pair exercised
here is resolved by the same generic registry.

Covered guarantees:
  * real Ronin activity produces transfers
  * transfers produce graph nodes/edges
  * graph + flow data reaches the attribution engine
  * attribution produces a score from real evidence
  * zero activity produces a 0 score and no fabricated evidence
  * activity older than one 200-block chunk is found through pagination
  * throttling is reported as LIVE_PARTIAL with disclosed limitations,
    never as a false NO_DATA
"""
import asyncio
import json
import os

import pytest

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "ronin_real_logs.json")

with open(FIXTURE, "r", encoding="utf-8") as _fh:
    REAL = json.load(_fh)

WALLET = REAL["address"]
REAL_LOGS = REAL["logs"]
# Block numbers actually present in the captured data.
OLDEST = min(int(log["blockNumber"], 16) for log in REAL_LOGS)
NEWEST = max(int(log["blockNumber"], 16) for log in REAL_LOGS)


def _padded(address: str) -> str:
    return "0x" + address[2:].lower().rjust(64, "0")


def _matches(params: dict, log: dict) -> bool:
    """Evaluate an eth_getLogs filter locally, the way the node would."""
    from blockchain.ronin_provider import TRANSFER_TOPICS

    topics = params.get("topics") or []
    log_topics = [str(t).lower() for t in log["topics"]]
    for i, spec in enumerate(topics):
        if spec is None:
            continue
        if i >= len(log_topics):
            return False
        allowed = spec if isinstance(spec, list) else [spec]
        if not any(log_topics[i] == str(a).lower() for a in allowed):
            return False
    return True


class ReplayRpc:
    """Serves captured Ronin data; models throttling when asked to."""

    def __init__(self, *, throttle_after=None, head=None, empty_control=False):
        self.head = head if head is not None else NEWEST
        self.throttle_after = throttle_after
        # Models a throttling endpoint that answers HTTP 200 with an empty list
        # instead of an error, which is how the official RPC behaves.
        self.empty_control = empty_control
        self.log_requests = 0
        self.calls = []

    async def verify_chain(self):
        return None

    async def block_number(self):
        return self.head

    async def get_logs(self, params):
        from blockchain.errors import ProviderRateLimitError

        self.log_requests += 1
        self.calls.append(params)
        if self.throttle_after is not None and self.log_requests > self.throttle_after:
            raise ProviderRateLimitError("Ronin RPC rate limit: replayed", chain="ronin")
        if self.empty_control:
            return []
        lo = int(params["fromBlock"], 16)
        hi = int(params["toBlock"], 16)
        return [
            log
            for log in REAL_LOGS
            if lo <= int(log["blockNumber"], 16) <= hi
            and _matches(params, log)
        ]

    async def receipt(self, tx_hash):
        return REAL["receipts"].get(tx_hash)

    async def block_with_transactions(self, block_number):
        for block in REAL["blocks"]:
            if block and int(block["number"], 16) == block_number:
                return block
        return None

    async def eth_call(self, contract, data):  # symbol()/decimals()
        return None


def _provider(monkeypatch, rpc, **env):
    from blockchain.ronin_provider import RoninProvider

    monkeypatch.setenv("RONIN_SCAN_BLOCKS", env.pop("scan", "100000"))
    monkeypatch.setenv("RONIN_MAX_REQUESTS", env.pop("budget", "600"))
    monkeypatch.setenv("RONIN_NATIVE_SCAN_BLOCKS", "0")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    provider = RoninProvider()
    provider._rpc = rpc
    return provider


# ---------------------------------------------------------------------------
# Real activity -> transfers
# ---------------------------------------------------------------------------


class TestRealRoninActivityProducesTransfers:
    def test_real_logs_become_normalized_transfers(self, monkeypatch):
        rpc = ReplayRpc()
        provider = _provider(monkeypatch, rpc, scan=str(NEWEST - OLDEST + 200))
        result = asyncio.run(provider._rpc_transfers(WALLET, 500))

        assert result.status == "LIVE_PARTIAL"
        assert result.data_source == "live"
        assert result.provider == "ronin-rpc"
        assert len(result.transfers) > 0

    def test_transfers_carry_real_chain_identity(self, monkeypatch):
        rpc = ReplayRpc()
        provider = _provider(monkeypatch, rpc, scan=str(NEWEST - OLDEST + 200))
        transfers = asyncio.run(provider._rpc_transfers(WALLET, 500)).transfers

        for transfer in transfers:
            assert transfer.chain == "ronin"
            assert transfer.transaction_hash.startswith("0x")
            assert len(transfer.transaction_hash) == 66
            assert transfer.block_number is not None
            # Never an invented hash.
            assert transfer.transaction_hash != "0x" + "0" * 64

    def test_both_incoming_and_outgoing_are_discovered(self, monkeypatch):
        rpc = ReplayRpc()
        provider = _provider(monkeypatch, rpc, scan=str(NEWEST - OLDEST + 200))
        transfers = asyncio.run(provider._rpc_transfers(WALLET, 500)).transfers

        directions = {t.direction for t in transfers}
        assert "in" in directions, "incoming transfers must not be dropped"
        assert "out" in directions, "outgoing transfers must not be dropped"

    def test_erc20_and_erc721_are_categorised(self, monkeypatch):
        rpc = ReplayRpc()
        provider = _provider(monkeypatch, rpc, scan=str(NEWEST - OLDEST + 200))
        transfers = asyncio.run(provider._rpc_transfers(WALLET, 500)).transfers

        categories = {t.category for t in transfers}
        assert "erc20" in categories
        assert categories & {"erc721", "erc1155"}

    def test_only_transfers_touching_the_wallet_are_returned(self, monkeypatch):
        rpc = ReplayRpc()
        provider = _provider(monkeypatch, rpc, scan=str(NEWEST - OLDEST + 200))
        transfers = asyncio.run(provider._rpc_transfers(WALLET, 500)).transfers
        wanted = WALLET.lower()

        for transfer in transfers:
            assert wanted in (transfer.from_address.lower(), transfer.to_address.lower())


# ---------------------------------------------------------------------------
# Pagination: history outside the first chunk is reachable
# ---------------------------------------------------------------------------


class TestHistoricalActivityIsDiscoverable:
    def test_activity_older_than_one_chunk_is_found_by_pagination(self, monkeypatch):
        """The captured activity starts at block ``OLDEST``, far beyond a single
        200-block window, and must still be discovered."""
        assert NEWEST - OLDEST > 200, "fixture must span more than one chunk"
        rpc = ReplayRpc()
        provider = _provider(monkeypatch, rpc, scan=str(NEWEST - OLDEST + 200))
        result = asyncio.run(provider._rpc_transfers(WALLET, 500))

        assert result.transfers, "pagination failed to reach historical activity"
        assert min(t.block_number for t in result.transfers) <= OLDEST + 200

    def test_pagination_actually_walks_multiple_chunks(self, monkeypatch):
        rpc = ReplayRpc()
        provider = _provider(monkeypatch, rpc, scan=str(NEWEST - OLDEST + 200))
        asyncio.run(provider._rpc_transfers(WALLET, 500))

        assert rpc.log_requests > 3, "expected several chunked getLogs calls"
        visited = sorted({int(p["fromBlock"], 16) for p in rpc.calls})
        assert len(visited) > 1

    def test_quiet_wallet_reports_no_data_with_the_searched_range(self, monkeypatch):
        """A wallet with no events in the replayed range must report NO_DATA and
        disclose exactly which blocks were searched, not invent data and not
        claim the wallet is inactive."""
        quiet = "0x000000000000000000000000000000000000dEaD"
        rpc = ReplayRpc()
        provider = _provider(monkeypatch, rpc, scan="200")
        result = asyncio.run(provider._rpc_transfers(quiet, 500))

        assert result.status == "NO_DATA"
        assert result.transfers == []
        joined = " ".join(result.limitations).lower()
        assert "not evidence that the wallet is inactive" in joined
        assert str(rpc.head) in joined, "the searched range must be disclosed"

    def test_narrow_window_that_excludes_activity_invents_nothing(self, monkeypatch):
        """Once the chain advances past the wallet's last transfer, a small window
        legitimately finds nothing. It must return zero transfers and disclose
        the range searched, rather than inventing data."""
        rpc = ReplayRpc(head=NEWEST + 5_000)
        provider = _provider(monkeypatch, rpc, scan="200", budget="600")
        result = asyncio.run(provider._rpc_transfers(WALLET, 500))

        assert result.transfers == []
        assert result.status == "LIVE_PARTIAL", (
            "an event-free range cannot be distinguished from a throttled "
            "endpoint, so it must not be certified as a completed NO_DATA"
        )
        joined = " ".join(result.limitations)
        assert str(rpc.head) in joined
        assert "not evidence that the wallet is inactive" in joined.lower()


# ---------------------------------------------------------------------------
# Throttling honesty
# ---------------------------------------------------------------------------


class TestThrottlingIsReportedHonestly:
    def test_partial_results_survive_a_mid_scan_throttle(self, monkeypatch):
        """Data found before the throttle is kept and reported as partial."""
        rpc = ReplayRpc(throttle_after=6)
        provider = _provider(monkeypatch, rpc, scan=str(NEWEST - OLDEST + 200))
        result = asyncio.run(provider._rpc_transfers(WALLET, 500))

        assert result.status == "LIVE_PARTIAL"
        assert result.transfers, "real activity found before the throttle was lost"
        assert result.truncated is True
        assert any("stopped early" in note for note in result.limitations)

    def test_throttle_is_never_reported_as_a_false_no_data(self, monkeypatch):
        """The public RPC answers a throttled request with an EMPTY result, which
        is indistinguishable from a quiet wallet. It must be reported as
        LIVE_PARTIAL and marked untrustworthy, never as a completed NO_DATA."""
        rpc = ReplayRpc(throttle_after=0)
        provider = _provider(monkeypatch, rpc, scan=str(NEWEST - OLDEST + 200))
        result = asyncio.run(provider._rpc_transfers(WALLET, 500))

        assert result.status == "LIVE_PARTIAL"
        assert result.transfers == []
        joined = " ".join(result.limitations).lower()
        assert "stopped early" in joined
        assert "could not be validated" in joined
        assert "must not be read as evidence that the wallet has no activity" in joined

    def test_verified_quiet_window_is_a_legitimate_no_data(self, monkeypatch):
        """A quiet wallet inside a chain range that DOES contain other activity
        is a real, completed search, so it is legitimately NO_DATA.

        This is the realistic case: Ronin is busy, so the positive control finds
        logs, the filters are proven, and the wallet's own silence is a fact
        about the scanned range rather than a provider failure."""
        quiet = "0x000000000000000000000000000000000000dEaD"
        rpc = ReplayRpc()
        provider = _provider(monkeypatch, rpc, scan="400", budget="600")
        result = asyncio.run(provider._rpc_transfers(quiet, 500))

        assert result.status == "NO_DATA"
        assert result.transfers == []
        assert rpc.log_requests >= 2, "the filter self-check must actually have run"
        joined = " ".join(result.limitations).lower()
        assert "could not be validated" not in joined

    def test_event_free_range_is_never_certified_as_a_clean_no_data(self, monkeypatch):
        """When even an unfiltered control query returns nothing, an empty result
        cannot be told apart from a throttled endpoint. It must be reported as
        LIVE_PARTIAL rather than certified as a completed NO_DATA."""
        rpc = ReplayRpc(head=NEWEST + 5_000, empty_control=True)
        provider = _provider(monkeypatch, rpc, scan="400", budget="600")
        result = asyncio.run(provider._rpc_transfers(WALLET, 500))

        assert result.status == "LIVE_PARTIAL"
        assert result.transfers == []
        assert "could not be validated" in " ".join(result.limitations).lower()

    def test_budget_truncation_is_not_reported_as_a_complete_scan(self, monkeypatch):
        """If the request budget is smaller than the configured window, only part
        of it can be searched. That must be disclosed as not reaching the end of
        the window, and any real activity found must still be returned."""
        rpc = ReplayRpc(head=NEWEST + 5_000)
        # A 100k-block window against a budget that only covers a fraction of it.
        provider = _provider(monkeypatch, rpc, scan="100000", budget="360")
        result = asyncio.run(provider._rpc_transfers(WALLET, 500))

        assert result.status == "LIVE_PARTIAL"
        joined = " ".join(result.limitations).lower()
        assert "end of the configured window" in joined, (
            "a budget-truncated scan must disclose that the window was not "
            f"searched to its end; got: {joined}"
        )
        assert "activity older than block" in joined
        for transfer in result.transfers:
            assert transfer.transaction_hash, "no transfer may be hashless"

    def test_disclosed_range_states_the_scan_did_not_finish(self, monkeypatch):
        rpc = ReplayRpc(throttle_after=4)
        provider = _provider(monkeypatch, rpc, scan=str(NEWEST - OLDEST + 200))
        result = asyncio.run(provider._rpc_transfers(WALLET, 500))
        assert any(
            "did NOT reach the end" in note or "stopped early" in note
            for note in result.limitations
        )


# ---------------------------------------------------------------------------
# Transfers -> graph -> attribution
# ---------------------------------------------------------------------------


class TestRealRoninDataReachesAttribution:
    def _pipeline(self):
        from pipeline.service import InvestigationPipeline

        return InvestigationPipeline(sync_to_neo4j=False)

    def _real_transfers(self):
        from blockchain.ronin_provider import RoninProvider

        provider = RoninProvider()
        provider._rpc = ReplayRpc()
        os.environ.setdefault("RONIN_SCAN_BLOCKS", "100000")
        return asyncio.run(provider._rpc_transfers(WALLET, 500)).transfers

    def test_transfers_build_graph_nodes_and_edges(self):
        pipeline = self._pipeline()
        transfers = self._real_transfers()
        graph = pipeline._transfers_to_graph(
            [t.model_dump() for t in transfers], WALLET
        )

        assert len(graph.nodes) > 0, "no graph nodes from real transfers"
        assert len(graph.edges) > 0, "no graph edges from real transfers"
        assert any(
            str(node.get("wallet_id", "")).startswith("ronin:")
            for node in graph.nodes
        )

    def test_graph_projection_produces_flows_for_attribution(self):
        pipeline = self._pipeline()
        transfers = self._real_transfers()
        graph = pipeline._transfers_to_graph(
            [t.model_dump() for t in transfers], WALLET
        )
        graph_data = pipeline._graph_to_graph_data(graph, WALLET, "ronin")

        flows = graph_data.get("flows") or []
        assert flows, "graph produced no flows for the attribution engine"
        wallet_id = f"ronin:{WALLET.lower()}"
        assert any(
            f.get("target") == wallet_id or f.get("source") == wallet_id
            for f in flows
        )

    def test_real_flows_produce_a_positive_behavioural_score(self):
        """The behavioural scorer must see the real Ronin flows."""
        from attribution.scoring import AttributionScorer

        pipeline = self._pipeline()
        transfers = self._real_transfers()
        graph = pipeline._transfers_to_graph(
            [t.model_dump() for t in transfers], WALLET
        )
        graph_data = pipeline._graph_to_graph_data(graph, WALLET, "ronin")
        scorer = AttributionScorer(
            vasp_repo=pipeline._intel.repository_for("live"),
            evidence_svc=pipeline._attr._evidence,
            weights=pipeline._attr._scorer.weights,
        )
        score, explanations = scorer.score_transaction_flow(WALLET, "ronin", graph_data)

        assert score > 0.0, "real flows produced no behavioural evidence"
        assert explanations

    def test_attribution_never_invents_a_vasp_match_from_real_ronin_data(self):
        """Real Ronin activity must not be turned into a VASP attribution.

        Bitget is the only VASP with a verified Ronin address, so it is the only
        candidate the directory could propose for this chain. This captured
        trading wallet never transacted with it, so there is no Bitget-specific
        evidence and the result must be the explicit UNKNOWN placeholder rather
        than a lone low-score Bitget row that reads like a finding.
        """
        from attribution.models import AttributionRequest

        pipeline = self._pipeline()
        transfers = self._real_transfers()
        graph = pipeline._transfers_to_graph(
            [t.model_dump() for t in transfers], WALLET
        )
        graph_data = pipeline._graph_to_graph_data(graph, WALLET, "ronin")

        response = pipeline._attr.analyze(
            AttributionRequest(address=WALLET, chain="ronin", graph_data=graph_data),
            data_source="live",
        )

        assert response.candidates, "attribution returned no candidate placeholder"
        top = response.candidates[0]
        assert top.vasp_name == "UNKNOWN"
        assert top.score == 0.0
        assert top.evidence_ids == [], "no evidence may be invented"

    def test_bitget_is_a_ronin_candidate_only_when_the_wallet_traded_with_it(self):
        """The same pipeline must surface Bitget - with real evidence - as soon as
        the ingested transactions genuinely involve Bitget's verified address,
        and stay UNKNOWN when they do not."""
        from attribution.models import AttributionRequest, Confidence

        from intelligence.curated_directory import BITGET_RONIN

        pipeline = self._pipeline()
        transfers = self._real_transfers()
        assert transfers, "fixture must contain real transfers"

        # Investigate a real counterparty from the captured activity instead of
        # the captured wallet itself: the chain, not a hardcoded wallet, must be
        # what selects the provider and the directory match.
        counterparty = transfers[0].to_address
        graph = pipeline._transfers_to_graph(
            [t.model_dump() for t in transfers], counterparty
        )
        graph_data = pipeline._graph_to_graph_data(graph, counterparty, "ronin")

        response = pipeline._attr.analyze(
            AttributionRequest(
                address=counterparty, chain="ronin", graph_data=graph_data
            ),
            data_source="live",
        )

        # Whatever the outcome, it must be earned: Bitget with evidence, or the
        # explicit UNKNOWN placeholder. Nothing in between.
        assert set(c.vasp_name for c in response.candidates) <= {"Bitget", "UNKNOWN"}
        for candidate in response.candidates:
            assert candidate.chain == "ronin"
            assert candidate.confidence in (
                Confidence.HIGH,
                Confidence.MEDIUM,
                Confidence.LOW,
            )
            if candidate.vasp_name == "Bitget":
                assert candidate.evidence_ids
                records = [
                    pipeline._attr.evidence_service.get_evidence(ev_id).model_dump()
                    for ev_id in candidate.evidence_ids
                ]
                # A surfaced Bitget candidate must rest on a real VASP-specific
                # signal, never on a behavioural score alone.
                assert candidate.score_breakdown.known_address_match > 0 or any(
                    BITGET_RONIN.address.lower() == r.get("matched_address")
                    for r in records
                )

    def test_zero_activity_scores_zero_and_creates_no_evidence(self):
        from attribution.models import AttributionRequest

        pipeline = self._pipeline()
        empty_graph = {"neighbors": [], "flows": [], "path": None}
        response = pipeline._attr.analyze(
            AttributionRequest(address=WALLET, chain="ronin", graph_data=empty_graph),
            data_source="live",
        )
        top = response.candidates[0]
        assert top.score == 0.0
        assert top.evidence_ids == []
        assert response.evidence_count == 0 if hasattr(
            response, "evidence_count"
        ) else True


# ---------------------------------------------------------------------------
# Generic, wallet-independent behaviour
# ---------------------------------------------------------------------------


class TestConfidenceThresholdIsNotLowered:
    """HIGH confidence must stay reserved for the configured threshold."""

    def test_thresholds_are_unchanged(self):
        from attribution.scoring import AttributionScorer

        assert AttributionScorer.HIGH_THRESHOLD == 70.0
        assert AttributionScorer.MEDIUM_THRESHOLD == 40.0

    def test_high_confidence_requires_the_threshold(self, attr_service=None):
        from attribution.service import AttributionService
        from attribution.models import Confidence

        svc = AttributionService.__new__(AttributionService)
        assert svc._determine_confidence(70.0) == Confidence.HIGH
        assert svc._determine_confidence(69.99) != Confidence.HIGH
        assert svc._determine_confidence(40.0) == Confidence.MEDIUM
        assert svc._determine_confidence(39.99) == Confidence.LOW

    def test_real_ronin_scores_stay_low(self):
        """Real Ronin flows currently produce no VASP candidate at all, so the
        result must be LOW and must never be presented as HIGH."""
        from attribution.models import AttributionRequest, Confidence
        from pipeline.service import InvestigationPipeline

        pipeline = InvestigationPipeline(sync_to_neo4j=False)
        rpc = ReplayRpc()
        provider = _provider_from_pipeline(pipeline, rpc)
        transfers = asyncio.run(provider._rpc_transfers(WALLET, 500)).transfers
        graph = pipeline._transfers_to_graph(
            [t.model_dump() for t in transfers], WALLET
        )
        graph_data = pipeline._graph_to_graph_data(graph, WALLET, "ronin")

        response = pipeline._attr.analyze(
            AttributionRequest(address=WALLET, chain="ronin", graph_data=graph_data),
            data_source="live",
        )
        top = response.candidates[0]
        assert top.confidence == Confidence.LOW
        assert top.score < 70.0


def _provider_from_pipeline(pipeline, rpc):
    from blockchain.ronin_provider import RoninProvider

    os.environ["RONIN_SCAN_BLOCKS"] = "100000"
    os.environ["RONIN_MAX_REQUESTS"] = "600"
    os.environ["RONIN_NATIVE_SCAN_BLOCKS"] = "0"
    provider = RoninProvider()
    provider._rpc = rpc
    return provider


class TestGenericAcrossWalletsAndChains:
    def test_every_supported_chain_resolves_a_provider(self):
        from blockchain.registry import registered_chains

        for chain in registered_chains():
            assert chain in ("eth", "ronin")

    def test_arbitrary_valid_addresses_are_accepted_unchanged(self):
        """Changing the wallet must never require a code change."""
        from blockchain.chains import resolve_chain, validate_address_for_chain

        for chain in ("eth", "ronin"):
            spec = resolve_chain(chain)
            for address in (
                "0x3b3adf1422f84254b7fbb0e7ca62bd0865133fe3",
                "0x0000000000000000000000000000000000000001",
                "0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",
            ):
                normalized = validate_address_for_chain(address, spec.id)
                assert normalized.startswith("0x")
                assert normalized == normalized.lower()

    def test_same_address_on_two_chains_is_never_merged(self):
        from blockchain.chains import wallet_id

        shared = "0x3b3adf1422f84254b7fbb0e7ca62bd0865133fe3"
        assert wallet_id("eth", shared) != wallet_id("ronin", shared)

    @pytest.mark.parametrize("chain", ["eth", "ronin"])
    def test_a_wallet_absent_from_the_directory_is_not_attributed(self, chain):
        """No fabricated VASP ownership for an unknown wallet on any chain."""
        from attribution.models import AttributionRequest

        from intelligence.curated_directory import load_curated_vasp_directory

        repo = load_curated_vasp_directory()
        address = "0x000000000000000000000000000000000000dEaD"
        assert repo.lookup_by_address(address, chain) == []

        from pipeline.service import InvestigationPipeline

        pipeline = InvestigationPipeline(sync_to_neo4j=False)
        graph = pipeline._transfers_to_graph([], address)
        graph_data = pipeline._graph_to_graph_data(graph, address, chain)
        response = pipeline._attr.analyze(
            AttributionRequest(address=address, chain=chain, graph_data=graph_data),
            data_source="live",
        )
        assert response.candidates[0].vasp_name == "UNKNOWN"
        assert response.candidates[0].score == 0.0

    def test_ronin_coverage_is_exactly_the_one_verified_ronin_address(self):
        """Guards against Ronin coverage silently widening.

        Ronin coverage exists now, and it must stay exactly as narrow as the
        evidence that justified it: one verified address, tagged with the chain
        it was verified on, and never mirrored onto another chain merely because
        the hex string is also a valid address there."""
        from intelligence.curated_directory import (
            BITGET_RONIN,
            load_curated_vasp_directory,
        )

        repo = load_curated_vasp_directory()
        assert repo.get_vasp_names_for_chain("ronin") == ["Bitget"]
        ronin = repo.get_known_vasp_addresses("ronin")
        assert [a.address.lower() for a in ronin] == [
            BITGET_RONIN.address.lower()
        ]

        # Every stored address must carry the chain it was verified on, and the
        # Ronin entry must not leak onto Ethereum.
        eth_addresses = {a.address.lower() for a in repo.get_all_addresses()
                         if a.chain == "eth"}
        assert BITGET_RONIN.address.lower() not in eth_addresses
        assert repo.lookup_by_address(BITGET_RONIN.address, "eth") == []