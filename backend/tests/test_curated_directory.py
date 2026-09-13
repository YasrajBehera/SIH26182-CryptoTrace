"""Curated public VASP directory contract for LIVE attribution.

The curated directory contains real, publicly documented exchange addresses
(sourced from public block-explorer labels and Bitfinex's published wallet
list). It is used ONLY for live investigations; the synthetic seed remains the
demo/test reference. The two must never mix: an address matched by the curated
directory in demo mode, or by synthetic data in live mode, would be a false
attribution.
"""

from intelligence.curated_directory import load_curated_vasp_directory
from intelligence.synthetic_data import seed_synthetic_vasp_data


class TestCuratedDirectory:
    def test_loads_public_entities(self):
        repo = load_curated_vasp_directory()
        names = {e.name for e in repo.get_all_entities()}
        assert {"Coinbase", "Binance", "Kraken", "Gemini"} <= names

    def test_eth_addresses_are_verified_public_wallets(self):
        repo = load_curated_vasp_directory()
        eth = repo.get_known_vasp_addresses("eth")
        addresses = {a.address.lower() for a in eth}
        # Two well-known public exchange hot wallets.
        assert "0x71660c4005ba85c37ccec55d0c4493e66fe775d3" in addresses
        assert "0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be" in addresses
        assert all(a.source in {"etherscan", "bscscan", "bitfinex-published"} for a in eth)

    def test_no_synthetic_names_leak_into_curated_directory(self):
        curated = load_curated_vasp_directory()
        synthetic = seed_synthetic_vasp_data()
        curated_names = {e.name for e in curated.get_all_entities()}
        synthetic_names = {e.name for e in synthetic.get_all_entities()}
        assert curated_names.isdisjoint(synthetic_names)

    def test_directory_is_small_and_conservative(self):
        # Deliberately a reference aid, not an exhaustive registry.
        repo = load_curated_vasp_directory()
        assert len(repo.get_all_addresses()) <= 16


class TestIntelligenceModeRouting:
    def test_live_uses_curated_repo(self):
        from intelligence.service import VASPIntelligenceService

        svc = VASPIntelligenceService()
        assert svc.repository_for("live") is svc.curated_repository
        assert svc.repository_for("demo") is svc.repository

    def test_live_lookup_matches_real_public_address(self):
        from intelligence.service import VASPIntelligenceService

        svc = VASPIntelligenceService()
        result = svc.lookup_address(
            "0x71660c4005BA85c37ccec55d0C4493E66Fe775d3",
            "eth",
            data_source="live",
        )
        assert result.is_known_vasp is True
        assert result.known_vasp == "Coinbase"
        assert result.verification_status == "verified"

    def test_live_lookup_ignores_synthetic_seed(self):
        from intelligence.service import VASPIntelligenceService

        svc = VASPIntelligenceService()
        # Demo-only address must not resolve to anything in live mode.
        result = svc.lookup_address(
            "0xaabb000000000000000000000000000000000001",
            "eth",
            data_source="live",
        )
        assert result.is_known_vasp is False
        assert result.known_vasp is None

    def test_demo_lookup_ignores_curated_directory(self):
        from intelligence.service import VASPIntelligenceService

        svc = VASPIntelligenceService()
        result = svc.lookup_address(
            "0x71660c4005BA85c37ccec55d0C4493E66Fe775d3",
            "eth",
            data_source="demo",
        )
        assert result.is_known_vasp is False