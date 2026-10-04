"""Chain-scoped VASP matching, attribution honesty and evidence traceability.

Covers the verified Ronin VASP entry end to end and, just as importantly, the
cases where the system must answer UNKNOWN instead of naming a VASP.

Everything asserted here is chain-generic. The Bitget Ronin address is an entry
in the curated reference directory like any other; nothing in the product code
treats it, the wallet under investigation, or the chain specially. The network is
stubbed, in the same style as ``test_pipeline_modes``, and the one real artefact
replayed is the Ronin explorer transaction the directory label was verified
against.

Guarantees pinned by this module:
  1. the verified Bitget Ronin address is recognised as VERIFIED
  2. an address is only ever matched on the chain it was verified for
  3. Ronin address normalization is case/whitespace insensitive
  4. the real verification transaction hash reaches the evidence
  5. a Ronin wallet with no VASP relationship stays UNKNOWN
  6. a no-flow wallet scores 0
  7. HIGH still requires >= 70 and MEDIUM >= 40
  8. every wallet and chain alias runs the identical pipeline
  9. unverified directory entries can never produce a known-VASP attribution
 10. Ethereum behaviour is unchanged
11. a bounded Ronin scan is reported LIVE_PARTIAL and discloses truncation
  12. no synthetic address or entity can reach LIVE attribution
  13. real, repeated VASP interactions reach HIGH, and every band in between is
      earned by observed evidence rather than by moving a threshold
  14. a verified address match alone is still not HIGH
"""

from pathlib import Path

import pytest
from evidence.models import EvidenceType

import attribution.scoring as scoring_module
from attribution.models import AttributionRequest, Confidence
from attribution.scoring import AttributionScorer, ScoringWeights
from attribution.service import AttributionService
from blockchain.chains import normalize_address, wallet_id
from blockchain.models import BlockchainTransfer
from blockchain.providers import (
    SOURCE_LIVE,
    STATUS_LIVE,
    STATUS_LIVE_PARTIAL,
    BlockchainProvider,
    ProviderResult,
)
from evidence.repository import EvidenceRepository
from evidence.service import EvidenceService
from intelligence.curated_directory import BITGET_RONIN, load_curated_vasp_directory
from intelligence.models import VerificationStatus
from intelligence.service import VASPIntelligenceService
from intelligence.synthetic_data import seed_synthetic_vasp_data
from pipeline.models import InvestigationRequest
from pipeline.service import MODE_LIVE, InvestigationPipeline

# The verified Ronin transaction the Bitget directory label was checked against.
BITGET_TX = BITGET_RONIN.verification_tx_hash
BITGET_BLOCK = BITGET_RONIN.verification_block
BITGET_ADDR = BITGET_RONIN.address

# An unrelated Ronin trading account, used as the investigated wallet.
COUNTERPARTY = "0x7a4f5c3d2e1b0a9f8e7d6c5b4a3928170f6e5d4c"


def _hash(seed: int) -> str:
    return "0x" + f"{seed:064x}"


def _transfer(**overrides) -> BlockchainTransfer:
    base = dict(
        transaction_hash=_hash(1),
        block_number=BITGET_BLOCK,
        block_timestamp=1735689600,
        from_address=COUNTERPARTY,
        to_address=BITGET_ADDR,
        value="2770.21",
        asset="RON",
        category="external",
        direction="out",
        raw_contract_address=None,
        raw_contract_value=None,
        chain="ronin",
    )
    base.update(overrides)
    return BlockchainTransfer(**base)


def _bitget_transfers():
    """The verified transaction plus neighbouring activity on the same account."""
    transfers = [_transfer(transaction_hash=BITGET_TX)]
    for index in range(2, 7):
        transfers.append(
            _transfer(
                transaction_hash=_hash(index),
                block_number=BITGET_BLOCK + index,
                block_timestamp=1735689600 + index * 3600,
                to_address="0x" + f"{index:040x}",
            )
        )
    return transfers


def _other_transfers():
    """Activity that never touches a VASP address on this chain."""
    return [
        _transfer(
            transaction_hash=_hash(index),
            from_address=COUNTERPARTY,
            to_address="0x" + f"{index:040x}",
        )
        for index in range(2, 9)
    ]


def _repeated_bitget_transfers(count, step=3600, start=1735689600):
    """``count`` distinct real-shaped transfers with the verified VASP address.

    The quantity of observed transfers is the only thing that varies, so a test
    can state exactly how much evidence a given confidence band requires.
    """
    return [
        _transfer(
            transaction_hash=_hash(1000 + index),
            block_number=BITGET_BLOCK + index,
            block_timestamp=start + index * step,
        )
        for index in range(count)
    ]


def _flow(index, vasp_address=BITGET_ADDR, chain="ronin", start=1735689600):
    """One observed wallet<->VASP flow in the shape the scorer consumes."""
    wallet = f"{chain}:{COUNTERPARTY}"
    counterparty = f"{chain}:{vasp_address}"
    outbound = index % 2 == 0
    return {
        "source": wallet if outbound else counterparty,
        "target": counterparty if outbound else wallet,
        "amount": "100",
        "asset": "RON",
        "timestamp": start + index * 3600,
        "tx_hash": _hash(1000 + index),
    }


def _one_flow():
    return [_flow(0)]


class StubProvider(BlockchainProvider):
    """Serves a preset provider result; never touches a network."""

    def __init__(self, result, chain="ronin"):
        self.chain_name = chain
        self.provider_name = "stub"
        self._result = result
        self.requested_addresses = []

    async def get_transfers(self, address, limit=None):
        self.requested_addresses.append(address)
        return self._result


def _live_result(transfers, chain="ronin", status=STATUS_LIVE, **kwargs) -> ProviderResult:
    return ProviderResult(
        chain=chain,
        address=COUNTERPARTY,
        data_source=SOURCE_LIVE,
        status=status,
        provider="stub",
        transfers=list(transfers),
        **kwargs,
    )


class _Harness:
    """Pipeline plus the attribution and evidence stores it writes to.

    The pipeline is given its own ``AttributionService`` so the evidence ids a
    response advertises can be read back from the same store - the same
    relationship the app-wide singleton provides in production.
    """

    def __init__(self, provider_result, chain="ronin"):
        self.provider = StubProvider(provider_result, chain=chain)
        self.evidence = EvidenceService(EvidenceRepository())
        self.attribution = AttributionService(evidence_service=self.evidence)
        self.pipeline = InvestigationPipeline(
            sync_to_neo4j=False,
            provider_factory=lambda requested: self.provider,
            attribution_service=self.attribution,
        )
        self.result = None

    def run(self, address=COUNTERPARTY, chain="ronin", **kwargs):
        self.result = self.pipeline.run(
            InvestigationRequest(address=address, chain=chain),
            mode=MODE_LIVE,
            **kwargs,
        )
        return self.result

    def records_for(self, candidate):
        records = [
            self.evidence.get_evidence(ev_id) for ev_id in candidate.evidence_ids
        ]
        assert all(records), "every advertised evidence id must resolve"
        return records

    @property
    def stored_evidence_count(self):
        return self.evidence.repository.count()


def _harness(result, chain="ronin") -> _Harness:
    return _Harness(result, chain=chain)


def _run(result, address=COUNTERPARTY, chain="ronin", **kwargs):
    """Run the live pipeline and return only the ``InvestigationResult``."""
    return _harness(result, chain=chain).run(address=address, chain=chain, **kwargs)


def _ran(result, address=COUNTERPARTY, chain="ronin", **kwargs) -> _Harness:
    """Same, but hand back the harness so evidence records stay reachable."""
    harness = _harness(result, chain=chain)
    harness.run(address=address, chain=chain, **kwargs)
    return harness


def _counterparty_records(harness, candidate, vasp_address=BITGET_ADDR):
    """Evidence pointing at a specific VASP address on the analysed chain."""
    return [
        record
        for record in harness.records_for(candidate)
        if record.matched_address
        and record.matched_address.lower() == vasp_address.lower()
    ]


# ---------------------------------------------------------------------------
# 1. The verified Bitget Ronin address is recognised as VERIFIED
# ---------------------------------------------------------------------------


class TestVerifiedBitgetRoninEntry:
    def test_entry_is_verified_with_the_recorded_provenance(self):
        matches = load_curated_vasp_directory().lookup_by_address(BITGET_ADDR, "ronin")

        assert len(matches) == 1
        entry = matches[0]
        assert entry.vasp_name == "Bitget"
        assert entry.chain == "ronin"
        assert entry.verification_status == VerificationStatus.VERIFIED
        assert entry.source == "ronin official explorer"
        assert entry.source_url == "https://explorer.roninchain.com/"
        assert entry.confidence == pytest.approx(0.90)
        assert entry.evidence

    def test_entry_records_the_real_verification_transaction(self):
        assert BITGET_TX == (
            "0x733fc397a5a565a5f4ee16f15f420640a1a77982a87f12145634abf3e41ca8b2"
        )
        assert BITGET_BLOCK == 61_673_529
        assert len(BITGET_TX) == 66 and BITGET_TX.startswith("0x")

    def test_bitget_is_a_known_ronin_vasp_in_live_mode(self):
        result = VASPIntelligenceService().lookup_address(
            BITGET_ADDR, "ronin", data_source="live"
        )

        assert result.is_known_vasp is True
        assert result.known_vasp == "Bitget"
        assert result.verification_status == "verified"
        assert result.matched_address.lower() == BITGET_ADDR.lower()
        assert result.source_url == "https://explorer.roninchain.com/"

    def test_bitget_is_an_exchange_entity(self):
        repo = load_curated_vasp_directory()
        assert repo.get_vasp_names_for_chain("ronin") == ["Bitget"]
        entity = repo.get_entity("Bitget")
        assert entity is not None and entity.entity_type == "exchange"

    def test_ronin_is_the_only_chain_with_a_verified_bitget_address(self):
        chains = [
            a.chain for a in load_curated_vasp_directory().get_all_addresses()
            if a.vasp_name == "Bitget"
        ]
        assert chains == ["ronin"]

    def test_a_ronin_wallet_transacting_with_bitget_is_attributed_to_it(self):
        result = _run(_live_result(_bitget_transfers()))

        assert [c.vasp_name for c in result.candidates] == ["Bitget"]
        assert result.address_intelligence.known_vasp is None, (
            "the investigated wallet is not Bitget; the match is the counterparty"
        )


# ---------------------------------------------------------------------------
# 2. An address is only ever matched on the chain it was verified for
# ---------------------------------------------------------------------------


class TestChainScopedMatching:
    def test_bitget_address_does_not_match_on_ethereum(self):
        repo = load_curated_vasp_directory()
        assert repo.lookup_by_address(BITGET_ADDR, "eth") == []
        assert repo.lookup_by_address(BITGET_ADDR, "ethereum") == []

    @pytest.mark.parametrize("chain", ["eth", "bsc", "polygon"])
    def test_bitget_address_is_unknown_on_other_chains(self, chain):
        result = VASPIntelligenceService().lookup_address(
            BITGET_ADDR, chain, data_source="live"
        )
        assert result.is_known_vasp is False
        assert result.known_vasp is None

    def test_ethereum_entries_do_not_leak_into_ronin_lookups(self):
        repo = load_curated_vasp_directory()
        eth_addresses = [
            a.address for a in repo.get_all_addresses() if a.chain == "eth"
        ]
        assert eth_addresses, "the curated directory must contain Ethereum entries"
        for address in eth_addresses:
            assert repo.lookup_by_address(address, "ronin") == []

    def test_the_same_address_can_differ_per_chain(self):
        """``0xaabb...01`` is a seeded address on both Ethereum and BSC; neither
        entry may be returned for the other chain."""
        repo = seed_synthetic_vasp_data()
        assert repo.lookup_by_address("0xaabb000000000000000000000000000000000001", "eth")
        assert repo.lookup_by_address("0xaabb000000000000000000000000000000000001", "bsc")
        assert repo.lookup_by_address("0x1122000000000000000000000000000000000006", "eth")
        assert repo.lookup_by_address("0x1122000000000000000000000000000000000006", "bsc") == []

    def test_chain_aliases_resolve_to_the_same_entry(self):
        repo = load_curated_vasp_directory()
        for spelling in ("ronin", "RONIN", "ronin-mainnet", "Ronin Chain"):
            assert repo.lookup_by_address(BITGET_ADDR, spelling), spelling

    def test_wallet_identity_keeps_one_address_distinct_across_chains(self):
        assert wallet_id("ronin", BITGET_ADDR) != wallet_id("eth", BITGET_ADDR)


# ---------------------------------------------------------------------------
# 3. Address normalization
# ---------------------------------------------------------------------------


class TestAddressNormalization:
    def test_case_and_whitespace_variants_resolve_to_the_same_entry(self):
        repo = load_curated_vasp_directory()
        for spelling in (
            BITGET_ADDR,
            BITGET_ADDR.lower(),
            BITGET_ADDR.upper().replace("0X", "0x"),
            f"  {BITGET_ADDR}  ",
        ):
            assert repo.lookup_by_address(spelling, "ronin"), spelling

    def test_normalize_address_is_idempotent(self):
        once = normalize_address(f"  {BITGET_ADDR.upper()} ")
        assert once == normalize_address(once)
        assert once == BITGET_ADDR.lower()

    def test_normalize_address_tolerates_empty_input(self):
        assert normalize_address(None) == ""
        assert normalize_address("") == ""

    def test_pipeline_normalizes_the_requested_ronin_address(self):
        result = _run(_live_result(_bitget_transfers()), address=BITGET_ADDR.upper())
        assert result.address == BITGET_ADDR.lower()
        assert result.chain == "ronin"


# ---------------------------------------------------------------------------
# 4. The real verification transaction hash reaches the evidence
# ---------------------------------------------------------------------------


class TestVerificationTransactionIsTraceable:
    def test_direct_match_evidence_cites_the_verification_transaction(self):
        harness = _ran(_live_result(_bitget_transfers()), address=BITGET_ADDR)
        candidate = harness.result.candidates[0]
        known = [
            record
            for record in harness.records_for(candidate)
            if record.evidence_type == "known_address_match"
        ]

        assert known, "a direct directory match must produce evidence"
        assert known[0].matched_address.lower() == BITGET_ADDR.lower()
        assert BITGET_TX in known[0].description
        assert str(BITGET_BLOCK) in known[0].description

    def test_verification_tx_is_labelled_as_label_provenance_only(self):
        """The verification transaction attests the public label. It must never be
        presented as proof that the investigated wallet transacted with it."""
        harness = _ran(_live_result(_bitget_transfers()), address=BITGET_ADDR)
        known = next(
            record
            for record in harness.records_for(harness.result.candidates[0])
            if record.evidence_type == "known_address_match"
        )

        assert "attests the public label only" in known.description
        assert any(
            "not evidence of any transfer" in note for note in known.limitations
        ) or "not proof that the VASP controlled" in " ".join(known.limitations)

    def test_counterparty_evidence_cites_the_observed_transaction(self):
        harness = _ran(_live_result(_bitget_transfers()))
        candidate = harness.result.candidates[0]
        observed = _counterparty_records(harness, candidate)

        assert observed, "a transaction with Bitget must be recorded as evidence"
        assert observed[0].tx_hash == BITGET_TX
        assert BITGET_TX in observed[0].description

    def test_evidence_names_entity_chain_address_direction_value_and_source(self):
        harness = _ran(_live_result(_bitget_transfers()))
        record = _counterparty_records(harness, harness.result.candidates[0])[0]
        text = record.description

        assert "Bitget" in text
        assert "Ronin" in text
        assert BITGET_ADDR.lower() in text.lower()
        assert "direction out" in text
        assert "2770.21" in text
        assert "RON" in text
        assert BITGET_TX in text
        assert "ronin official explorer" in text

    def test_evidence_carries_chain_confidence_and_its_own_limitations(self):
        harness = _ran(_live_result(_bitget_transfers()))
        records = harness.records_for(harness.result.candidates[0])

        assert records
        for record in records:
            assert record.chain == "ronin"
            assert record.address == COUNTERPARTY
            assert record.source == "chain", "live evidence is not synthetic"
            assert 0.0 < record.confidence <= 1.0
            assert record.provenance.method == "attribution_engine_v1"
            assert record.limitations, "evidence must disclose what it does not prove"
            assert any(
                "does not by itself establish legal ownership" in note
                for note in record.limitations
            )

    def test_transactional_association_is_not_called_ownership(self):
        harness = _ran(_live_result(_bitget_transfers()))
        record = _counterparty_records(harness, harness.result.candidates[0])[0]
        joined = " ".join(record.limitations)

        assert "not proof that the VASP controlled" in joined
        assert "Only the scanned block range is covered" in joined

    def test_every_advertised_evidence_id_resolves_exactly_once(self):
        harness = _ran(_live_result(_bitget_transfers()))
        candidate = harness.result.candidates[0]

        assert candidate.evidence_ids
        assert len(set(candidate.evidence_ids)) == len(candidate.evidence_ids)
        assert harness.stored_evidence_count == len(candidate.evidence_ids)

    def test_no_evidence_is_minted_for_a_filtered_out_candidate(self):
        """Orphan evidence would describe a finding the response never shows."""
        harness = _ran(_live_result(_other_transfers()))

        assert [c.vasp_name for c in harness.result.candidates] == ["UNKNOWN"]
        assert harness.result.evidence_count == 0
        assert harness.stored_evidence_count == 0


# ---------------------------------------------------------------------------
# 5. Ronin wallets with no VASP relationship stay UNKNOWN
# ---------------------------------------------------------------------------


class TestUnknownWalletsStayUnknown:
    def test_wallet_with_no_vasp_counterparty_is_unknown(self):
        result = _run(_live_result(_other_transfers()))

        assert [c.vasp_name for c in result.candidates] == ["UNKNOWN"]
        assert result.candidates[0].score == 0.0
        assert result.candidates[0].evidence_ids == []
        assert result.address_intelligence.is_known_vasp is False

    def test_wallet_with_no_activity_at_all_is_unknown(self):
        result = _run(_live_result([]))

        assert [c.vasp_name for c in result.candidates] == ["UNKNOWN"]
        assert result.candidates[0].score == 0.0
        assert result.transfers_ingested == 0

    def test_unknown_placeholder_never_claims_ownership(self):
        result = _run(_live_result(_other_transfers()))

        assert result.candidates[0].confidence == Confidence.LOW
        assert "NOT proof of wallet ownership" in result.disclaimer


# ---------------------------------------------------------------------------
# 6. A no-flow wallet scores 0
# ---------------------------------------------------------------------------


class TestNoFlowScoresZero:
    @pytest.mark.parametrize("chain", ["eth", "ronin"])
    def test_empty_graph_produces_zero_and_no_evidence(self, chain):
        harness = _harness(_live_result([], chain=chain), chain=chain)
        response = harness.attribution.analyze(
            AttributionRequest(
                address=COUNTERPARTY,
                chain=chain,
                graph_data={"neighbors": [], "flows": []},
            ),
            data_source="live",
        )

        assert response.candidates[0].score == 0.0
        assert response.candidates[0].evidence_ids == []
        assert harness.stored_evidence_count == 0

    def test_flow_scorer_returns_zero_without_activity(self):
        harness = _harness(_live_result([]))
        score, explanations = harness.attribution.scorer.score_transaction_flow(
            COUNTERPARTY, "ronin", {"flows": [], "neighbors": []}
        )

        assert score == 0.0
        assert explanations


# ---------------------------------------------------------------------------
# 7. Thresholds are unchanged
# ---------------------------------------------------------------------------


class TestConfidenceThresholdsUnchanged:
    def test_threshold_values(self):
        assert AttributionScorer.HIGH_THRESHOLD == 70.0
        assert AttributionScorer.MEDIUM_THRESHOLD == 40.0

    @pytest.mark.parametrize(
        "score,expected",
        [
            (100.0, Confidence.HIGH),
            (70.0, Confidence.HIGH),
            (69.99, Confidence.MEDIUM),
            (40.0, Confidence.MEDIUM),
            (39.99, Confidence.LOW),
            (0.0, Confidence.LOW),
        ],
    )
    def test_boundary_behaviour(self, score, expected):
        harness = _harness(_live_result([]))
        assert harness.attribution._determine_confidence(score) == expected

    def test_the_real_bitget_transaction_stays_below_high(self):
        """A direct transaction with a verified VASP address is a real signal, but
        thresholds are not moved to manufacture a HIGH result."""
        result = _run(_live_result(_bitget_transfers()))
        candidate = result.candidates[0]

        assert candidate.confidence in (Confidence.MEDIUM, Confidence.LOW)
        assert candidate.score < AttributionScorer.HIGH_THRESHOLD
        assert candidate.score > 0.0


# ---------------------------------------------------------------------------
# 8. Every wallet and chain alias runs the identical pipeline
# ---------------------------------------------------------------------------


RONIN_WALLETS = [
    COUNTERPARTY,
    BITGET_ADDR,
    "0x3b3adf1422f84254b7fbb0e7ca62bd0865133fe3",
    "0x0000000000000000000000000000000000000001",
]


class TestGenericAcrossWalletsAndChains:
    @pytest.mark.parametrize("address", RONIN_WALLETS)
    def test_each_ronin_wallet_runs_the_same_pipeline(self, address):
        result = _run(_live_result(_bitget_transfers()), address=address)

        assert result.chain == "ronin"
        assert result.data_source == "live"
        assert result.analysis_id.startswith("attr-")
        assert result.transfers_ingested == len(_bitget_transfers())
        for candidate in result.candidates:
            assert candidate.chain == "ronin"
            assert candidate.address == normalize_address(address)

    def test_switching_wallet_requires_no_code_change(self):
        """The provider is chosen by chain and the directory match by
        ``(chain, address)``; two wallets, one code path, no branching."""
        counterparty = _run(_live_result(_bitget_transfers()), address=COUNTERPARTY)
        vasp_itself = _run(_live_result(_bitget_transfers()), address=BITGET_ADDR)

        assert counterparty.provider == vasp_itself.provider
        assert vasp_itself.candidates[0].vasp_name == "Bitget"
        assert (
            vasp_itself.candidates[0].score_breakdown.known_address_match
            > counterparty.candidates[0].score_breakdown.known_address_match
        )

    @pytest.mark.parametrize(
        "address,chain",
        [
            (COUNTERPARTY, "ronin"),
            (BITGET_ADDR, "ronin"),
            (COUNTERPARTY.upper(), "RONIN"),
            (COUNTERPARTY, "ronin-mainnet"),
        ],
    )
    def test_address_and_chain_aliases_need_no_code_change(self, address, chain):
        result = _run(_live_result(_bitget_transfers()), address=address, chain=chain)

        assert result.chain == "ronin"
        assert result.data_source == "live"
        assert result.address == normalize_address(address)


# ---------------------------------------------------------------------------
# 9. Unverified entries can never produce a known-VASP attribution
# ---------------------------------------------------------------------------


class TestUnverifiedEntriesCannotAttest:
    def test_unverified_entry_is_not_a_known_vasp(self):
        result = VASPIntelligenceService().lookup_address(
            "0x1122000000000000000000000000000000000006", "eth"
        )
        assert result.verification_status == "unverified"
        assert result.is_known_vasp is False

    def test_disputed_entry_is_not_a_known_vasp(self):
        result = VASPIntelligenceService().lookup_address(
            "0xdead00000000000000000000000000000000000d", "eth"
        )
        assert result.verification_status == "disputed"
        assert result.is_known_vasp is False

    def test_unverified_entry_cannot_be_a_candidate_from_a_live_directory(self):
        assert load_curated_vasp_directory().lookup_by_address(
            "0x1122000000000000000000000000000000000006", "eth"
        ) == []

    def test_only_verified_addresses_are_reachable_in_live_mode(self):
        repo = load_curated_vasp_directory()

        assert repo.get_all_addresses()
        assert all(
            entry.verification_status == VerificationStatus.VERIFIED
            for entry in repo.get_all_addresses()
        )
        assert all(
            entry.verification_status == VerificationStatus.VERIFIED
            for entry in repo.get_known_vasp_addresses("ronin")
        )


# ---------------------------------------------------------------------------
# 10. Ethereum behaviour is unchanged
# ---------------------------------------------------------------------------


COINBASE = "0x71660c4005BA85c37ccec55d0C4493E66Fe775d3"


class TestEthereumBehaviourUnchanged:
    def test_coinbase_still_matches_on_ethereum(self):
        result = VASPIntelligenceService().lookup_address(
            COINBASE, "eth", data_source="live"
        )
        assert result.known_vasp == "Coinbase"
        assert result.verification_status == "verified"
        assert result.is_known_vasp is True

    def test_ethereum_known_address_still_scores_with_evidence(self):
        harness = _harness(_live_result([], chain="eth"), chain="eth")
        response = harness.attribution.analyze(
            AttributionRequest(address=COINBASE, chain="eth"), data_source="live"
        )

        names = [c.vasp_name for c in response.candidates]
        assert "Coinbase" in names
        assert all(c.chain == "eth" for c in response.candidates)
        coinbase = next(c for c in response.candidates if c.vasp_name == "Coinbase")
        assert coinbase.score > 0.0
        assert coinbase.evidence_ids
        assert harness.stored_evidence_count == len(coinbase.evidence_ids)

    def test_ethereum_directory_roster_is_unchanged(self):
        repo = load_curated_vasp_directory()
        eth_addresses = {
            a.address.lower() for a in repo.get_all_addresses() if a.chain == "eth"
        }

        assert COINBASE.lower() in eth_addresses
        assert "0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be" in eth_addresses
        assert repo.get_vasp_names_for_chain("eth")


# ---------------------------------------------------------------------------
# 11. A bounded Ronin scan is LIVE_PARTIAL and discloses truncation
# ---------------------------------------------------------------------------

BOUNDED = (
    "The public Ronin RPC limits eth_getLogs to 200 blocks, so the scan was "
    "bounded and did NOT reach the end of the configured window. Activity older "
    f"than block {BITGET_BLOCK} may exist that was not ingested."
)


class TestBoundedRoninScanIsDisclosed:
    def test_bounded_scan_reports_live_partial(self):
        result = _run(
            _live_result(
                _bitget_transfers(),
                status=STATUS_LIVE_PARTIAL,
                truncated=True,
                limitations=[BOUNDED],
            )
        )

        assert result.status == "LIVE_PARTIAL"
        assert result.live_status == STATUS_LIVE_PARTIAL
        assert result.data_source == "live", "partial data is still real data"
        assert BOUNDED in result.limitations

    def test_truncation_is_stated_as_a_coverage_gap(self):
        result = _run(
            _live_result(
                _bitget_transfers(),
                status=STATUS_LIVE_PARTIAL,
                truncated=True,
                limitations=[BOUNDED],
            )
        )
        joined = " ".join(result.limitations).lower()

        assert "bounded" in joined
        assert "did not reach the end" in joined
        assert "may exist that was not ingested" in joined

    def test_bounded_scan_keeps_its_real_data_and_evidence(self):
        result = _run(
            _live_result(
                _bitget_transfers(),
                status=STATUS_LIVE_PARTIAL,
                truncated=True,
                limitations=[BOUNDED],
            )
        )

        assert result.transfers_ingested > 0
        assert result.candidates[0].vasp_name == "Bitget"
        assert result.candidates[0].evidence_ids

    def test_live_result_discloses_that_attribution_is_not_ownership(self):
        result = _run(_live_result(_bitget_transfers()))

        assert any(
            "does not establish wallet ownership" in note
            for note in result.limitations
        )

    def test_complete_scan_reports_live_without_a_coverage_warning(self):
        result = _run(_live_result(_bitget_transfers()))

        assert result.status == STATUS_LIVE
        assert result.live_status == STATUS_LIVE
        assert not any(
            "did not reach the end" in note for note in result.limitations
        )


# ---------------------------------------------------------------------------
# 12. No synthetic address or entity can reach LIVE attribution
# ---------------------------------------------------------------------------


SYNTHETIC_ADDRESSES = [
    "0xaabb000000000000000000000000000000000001",
    "0xaabb000000000000000000000000000000000002",
    "0xccdd000000000000000000000000000000000003",
    "0xefff000000000000000000000000000000000005",
    "0x3344000000000000000000000000000000000007",
    "0x1122000000000000000000000000000000000006",
]


class TestNoSyntheticAddressInLiveAttribution:
    @pytest.mark.parametrize("address", SYNTHETIC_ADDRESSES)
    def test_synthetic_address_is_unknown_to_the_live_directory(self, address):
        result = VASPIntelligenceService().lookup_address(
            address, "eth", data_source="live"
        )
        assert result.is_known_vasp is False
        assert result.known_vasp is None

    def test_live_attribution_never_names_a_synthetic_entity(self):
        synthetic_names = {
            e.name for e in seed_synthetic_vasp_data().get_all_entities()
        }
        result = _run(_live_result(_bitget_transfers()))

        assert not synthetic_names & {c.vasp_name for c in result.candidates}

    def test_live_evidence_source_is_chain_never_synthetic(self):
        harness = _ran(_live_result(_bitget_transfers()))
        records = harness.records_for(harness.result.candidates[0])

        assert records
        assert all(record.source == "chain" for record in records)

    def test_live_results_are_never_labelled_synthetic(self):
        result = _run(_live_result(_bitget_transfers()))

        assert result.data_source == "live"
        assert result.status in (STATUS_LIVE, STATUS_LIVE_PARTIAL)
        assert "synthetic" not in result.message.lower()
        assert "SYNTHETIC" not in result.status


# ---------------------------------------------------------------------------
# 13. Real evidence legitimately reaches HIGH (and no threshold is lowered)
# ---------------------------------------------------------------------------
#
# The HIGH threshold was never the problem. The problem was that two scoring
# components could not express the strongest real signal available:
#
#   * known_address_match (weight 0.35, the heaviest) returned 0.0 for every
#     wallet that was not itself a directory entry, so no amount of real
#     exchange activity could ever move it;
#   * transaction_flow scored only the *count* of counterparties, so a wallet
#     with 50 unrelated counterparties scored identically to one transacting
#     repeatedly with a verified VASP address.
#
# Together those two defects capped a Ronin wallet with real, repeated, on-chain
# VASP activity at ~50/100, making HIGH mathematically unreachable. Both now read
# the observed transfers. Everything below asserts the resulting bands are earned
# by evidence, not manufactured: no threshold moved, no score was multiplied, no
# wallet is special, and a verified address match on its own is still not HIGH.


def _candidate(result, vasp_name="Bitget"):
    return next(c for c in result.candidates if c.vasp_name == vasp_name)


class TestConfidenceIsEarnedByRealEvidence:
    def test_thresholds_are_untouched(self):
        assert AttributionScorer.HIGH_THRESHOLD == 70.0
        assert AttributionScorer.MEDIUM_THRESHOLD == 40.0

    def test_weights_are_applied_and_still_sum_to_one(self):
        weights = ScoringWeights().normalized()

        assert weights.model_dump() == {
            "graph_proximity": 0.25,
            "known_address_match": 0.35,
            "temporal_consistency": 0.15,
            "transaction_flow": 0.15,
            "cluster_evidence": 0.10,
        }
        assert sum(weights.model_dump().values()) == pytest.approx(1.0)

    def test_repeated_vasp_interactions_reach_high(self):
        result = _run(_live_result(_repeated_bitget_transfers(14)))
        candidate = _candidate(result)

        assert candidate.score >= AttributionScorer.HIGH_THRESHOLD
        assert candidate.confidence == Confidence.HIGH

    def test_high_score_is_composed_of_real_signals(self):
        result = _run(_live_result(_repeated_bitget_transfers(14)))
        candidate = _candidate(result)
        breakdown = candidate.score_breakdown

        # Every contributing component must reflect observed chain data.
        assert breakdown.known_address_match > 0.0
        assert breakdown.transaction_flow > 0.0
        assert breakdown.graph_proximity > 0.0
        assert breakdown.temporal_consistency > 0.0
        # Nothing was scored for a signal that was never observed.
        assert breakdown.cluster_evidence == 0.0

    def test_moderate_interactions_stay_medium(self):
        result = _run(_live_result(_repeated_bitget_transfers(3)))
        candidate = _candidate(result)

        assert AttributionScorer.MEDIUM_THRESHOLD <= candidate.score
        assert candidate.score < AttributionScorer.HIGH_THRESHOLD
        assert candidate.confidence == Confidence.MEDIUM

    def test_one_incidental_interaction_stays_low(self):
        result = _run(_live_result(_repeated_bitget_transfers(1)))
        candidate = _candidate(result)

        assert 0.0 < candidate.score < AttributionScorer.MEDIUM_THRESHOLD
        assert candidate.confidence == Confidence.LOW

    def test_no_vasp_relationship_stays_unknown(self):
        result = _run(_live_result(_other_transfers()))

        assert [c.vasp_name for c in result.candidates] == ["UNKNOWN"]
        assert result.candidates[0].score == 0.0
        assert result.candidates[0].evidence_ids == []

    def test_high_requires_more_than_the_verified_address_match_alone(self):
        """A verified directory match is strong, but it is not HIGH by itself.

        Scored on its own - no flows, no neighbours, no timing - the verified
        Ronin address yields only the address component's weighted contribution.
        """
        scorer = AttributionScorer(
            vasp_repo=load_curated_vasp_directory(), evidence_svc=EvidenceService()
        )
        score, _ = scorer.score_known_address_match(BITGET_ADDR, "ronin")
        weights = ScoringWeights().normalized()
        weighted = score * weights.known_address_match

        assert score == 90.0
        assert weighted < AttributionScorer.HIGH_THRESHOLD

    def test_verified_match_alone_does_not_report_high_end_to_end(self):
        harness = _harness(_live_result([]))
        response = harness.attribution.analyze(
            AttributionRequest(address=BITGET_ADDR, chain="ronin"),
            data_source="live",
        )
        bitget = next(c for c in response.candidates if c.vasp_name == "Bitget")

        assert bitget.score < AttributionScorer.HIGH_THRESHOLD
        assert bitget.confidence != Confidence.HIGH
        assert bitget.evidence_ids

    def test_band_depends_only_on_evidence_volume(self):
        """The same code produces every band purely from observed transfers."""
        scores = [
            _run(_live_result(_repeated_bitget_transfers(n))).candidates[0].score
            for n in (1, 3, 14)
        ]

        assert scores[0] < scores[1] < scores[2]
        assert scores[0] < AttributionScorer.MEDIUM_THRESHOLD
        assert scores[1] < AttributionScorer.HIGH_THRESHOLD
        assert scores[2] >= AttributionScorer.HIGH_THRESHOLD

    def test_repeated_interactions_score_higher_than_one_interaction(self):
        scorer = AttributionScorer(
            vasp_repo=load_curated_vasp_directory(), evidence_svc=EvidenceService()
        )
        one = scorer.score_known_address_match(
            COUNTERPARTY, "ronin", {"flows": _one_flow()}
        )[0]
        many = scorer.score_known_address_match(
            COUNTERPARTY,
            "ronin",
            {"flows": [_flow(index) for index in range(12)]},
        )[0]

        assert 0 < one < many


class TestHighAttributionIsTraceable:
    def test_every_high_signal_names_the_vasp_and_a_transaction(self):
        harness = _ran(_live_result(_repeated_bitget_transfers(14)))
        candidate = harness.result.candidates[0]

        assert candidate.confidence == Confidence.HIGH

        records = harness.records_for(candidate)
        assert records

        # Components that assert a link to a VASP must name it and cite a real
        # transaction; purely behavioural components must not borrow a tx hash.
        vasp_specific = {
            EvidenceType.KNOWN_ADDRESS_MATCH,
            EvidenceType.GRAPH_PROXIMITY,
            EvidenceType.TRANSACTION_FLOW,
        }
        linking = [r for r in records if r.evidence_type in vasp_specific]

        assert linking
        assert all(
            r.matched_address
            and r.matched_address.lower() == BITGET_ADDR.lower()
            for r in linking
        )
        assert any(r.tx_hash for r in linking)
        assert all(r.limitations for r in records)
        assert all(
            not r.tx_hash
            for r in records
            if r.evidence_type
            in (EvidenceType.TEMPORAL_CONSISTENCY, EvidenceType.CLUSTER_EVIDENCE)
        )

    def test_high_candidate_evidence_describes_real_transactions(self):
        harness = _ran(_live_result(_repeated_bitget_transfers(14)))
        candidate = harness.result.candidates[0]
        descriptions = " ".join(
            record.description for record in harness.records_for(candidate)
        )

        assert "Bitget" in descriptions
        assert str(BITGET_TX) not in descriptions  # not the verification tx
        assert any(
            _hash(1000 + index) in descriptions for index in range(14)
        ), "evidence must cite an observed wallet<->VASP transaction hash"

    def test_high_is_not_claimed_without_relevant_evidence(self):
        """A HIGH score alone cannot surface a VASP the wallet never touched."""
        result = _run(_live_result(_other_transfers()))

        assert all(c.confidence != Confidence.HIGH for c in result.candidates)


class TestIndirectSignalIsChainScopedAndGeneric:
    def test_observed_interaction_on_another_chain_contributes_nothing(self):
        """A Ronin VASP address must not score on an Ethereum investigation."""
        scorer = AttributionScorer(
            vasp_repo=load_curated_vasp_directory(), evidence_svc=EvidenceService()
        )
        eth_wallet = "0x1111111111111111111111111111111111111111"
        flows = [
            {
                "source": f"eth:{BITGET_ADDR}",
                "target": f"eth:{eth_wallet}",
                "amount": "10",
                "timestamp": 1735689600 + index,
                "tx_hash": _hash(1000 + index),
            }
            for index in range(14)
        ]

        score, explanations = scorer.score_known_address_match(
            eth_wallet, "eth", {"flows": flows}
        )

        assert score == 0.0
        assert any("not found in VASP database" in e for e in explanations)

    def test_ethereum_wallet_without_vasp_activity_is_unchanged(self):
        """Adding the indirect signal must not move Ethereum wallets with no VASP link."""
        scorer = AttributionScorer(
            vasp_repo=load_curated_vasp_directory(), evidence_svc=EvidenceService()
        )
        eth_wallet = "0x1111111111111111111111111111111111111111"
        unrelated = [
            {
                "source": f"eth:0x{i:040x}",
                "target": f"eth:{eth_wallet}",
                "amount": "10",
                "tx_hash": _hash(2000 + i),
            }
            for i in range(25)
        ]
        graph_data = {
            "flows": unrelated,
            "neighbors": [{"wallet_id": f"eth:0x{i:040x}"} for i in range(25)],
        }

        score, _ = scorer.score_known_address_match(eth_wallet, "eth", graph_data)
        flow, _ = scorer.score_transaction_flow(eth_wallet, "eth", graph_data)

        assert score == 0.0
        # Aggregate-counterparty behaviour is untouched: many unrelated
        # counterparties still scores as it always has.
        assert flow >= 70.0

    def test_ethereum_verified_address_still_scores_as_before(self):
        scorer = AttributionScorer(
            vasp_repo=load_curated_vasp_directory(), evidence_svc=EvidenceService()
        )

        score, explanations = scorer.score_known_address_match(COINBASE, "eth")

        assert score == 95.0
        assert any("Direct match: Coinbase" in e for e in explanations)

    def test_signal_is_generic_over_any_verified_vasp_not_just_bitget(self):
        """The mechanism is directory-driven, not entity-specific."""
        from intelligence.models import VASPAddress

        other = "0x0000000000000000000000000000000000000abc"
        repo = load_curated_vasp_directory()
        repo.add_address(
            VASPAddress(
                vasp_name="Other Exchange",
                address=other,
                chain="ronin",
                address_type="hot_wallet",
                source="test",
                source_url="https://example.invalid",
                confidence=0.8,
                verification_status=VerificationStatus.VERIFIED,
            )
        )
        scorer = AttributionScorer(vasp_repo=repo, evidence_svc=EvidenceService())
        flows = [
            {
                "source": f"ronin:{other}" if i % 2 else f"ronin:{COUNTERPARTY}",
                "target": f"ronin:{COUNTERPARTY}" if i % 2 else f"ronin:{other}",
                "amount": "10",
                "timestamp": 1735689600 + i * 3600,
                "tx_hash": _hash(3000 + i),
            }
            for i in range(14)
        ]
        graph_data = {"flows": flows, "neighbors": [{"wallet_id": f"ronin:{other}"}]}

        components = {
            "known_address_match": scorer.score_known_address_match(
                COUNTERPARTY, "ronin", graph_data
            )[0],
            "transaction_flow": scorer.score_transaction_flow(
                COUNTERPARTY, "ronin", graph_data
            )[0],
            "graph_proximity": scorer.score_graph_proximity(
                COUNTERPARTY, "ronin", [f"ronin:{other}"], None
            )[0],
            "temporal_consistency": scorer.score_temporal_consistency(
                COUNTERPARTY, "ronin", graph_data
            )[0],
        }
        weights = ScoringWeights().normalized()
        total = sum(
            components[name] * getattr(weights, name) for name in components
        )

        assert components["known_address_match"] > 0.0
        assert total >= AttributionScorer.HIGH_THRESHOLD

    def test_no_vasp_address_or_wallet_is_hardcoded_in_the_scorer(self):
        """The scorer must contain no address literal at all."""
        source = Path(scoring_module.__file__).read_text(encoding="utf-8")

        assert "0x" not in source
        assert "bitget" not in source.lower()
        assert "ronin" not in source.lower()