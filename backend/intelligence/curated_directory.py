"""Curated public VASP directory used for LIVE attribution.

Unlike the synthetic seed (which exists for demo/tests only), this directory
contains real, publicly documented VASP entities and exchange addresses. Every
address entry records the public source it was verified against.

This is a reference aid, NOT an exhaustive registry. It never claims custody
and it does not attempt to enumerate every wallet an exchange controls — the
small, curated set is intentionally conservative so a live candidate match
means "transacted with a publicly tagged VASP address", not "confirmed
ownership".

Address sources verified at time of writing:
  - Etherscan public exchange address labels (etherscan.io/accounts/label/*)
  - BscScan public labels
  - Bitfinex's published wallet list:
    https://github.com/bitfinexcom/pub/blob/main/wallets.txt
"""

from intelligence.models import AddressType, VerificationStatus, VASPAddress, VASPEntity
from intelligence.repository import VASPRepository

# (name, entity_type, jurisdiction) — jurisdiction is indicative per public
# registration/KYC disclosures and may drift; treat as "as publicly recorded".
_ENTITIES = [
    ("Binance", "exchange", "KY"),
    ("Coinbase", "exchange", "US"),
    ("Kraken", "exchange", "US"),
    ("Gemini", "exchange", "US"),
    ("Bitfinex", "exchange", "BVI"),
    ("Bitstamp", "exchange", "LU"),
    ("Crypto.com", "exchange", "SG"),
    ("OKX", "exchange", "SC"),
    ("Bybit", "exchange", "AE"),
    ("KuCoin", "exchange", "SC"),
    ("Gate.io", "exchange", "unknown"),
    ("HTX", "exchange", "unknown"),
]

# (address, chain, vasp_name, address_type, confidence, source)
_ADDRESSES = [
    (
        "0x3f5CE5FBFe3E9af3971dD833D26bA9b5C936f0bE",
        "eth",
        "Binance",
        AddressType.HOT_WALLET,
        0.95,
        "etherscan",
    ),
    (
        "0x3f5CE5FBFe3E9af3971dD833D26bA9b5C936f0bE",
        "bsc",
        "Binance",
        AddressType.HOT_WALLET,
        0.93,
        "bscscan",
    ),
    (
        "0x71660c4005BA85c37ccec55d0C4493E66Fe775d3",
        "eth",
        "Coinbase",
        AddressType.HOT_WALLET,
        0.95,
        "etherscan",
    ),
    (
        "0x2910543Af39abA0Cd09dBb2D50200b3E800A63D2",
        "eth",
        "Kraken",
        AddressType.HOT_WALLET,
        0.95,
        "etherscan",
    ),
    (
        "0x876EabF441B2EE5B5b0554Fd502a8E0600950cFa",
        "eth",
        "Bitfinex",
        AddressType.HOT_WALLET,
        0.93,
        "bitfinex-published",
    ),
    (
        "0xd24400AE8bFEBb18cA49BE86258A3c749cf46853",
        "eth",
        "Gemini",
        AddressType.HOT_WALLET,
        0.90,
        "etherscan",
    ),
    (
        "0x00BDb5699745f5b860228c8f939ABF1b9Ae374eD",
        "eth",
        "Bitstamp",
        AddressType.HOT_WALLET,
        0.88,
        "etherscan",
    ),
    (
        "0xA023f08c70A23aBc7EdFc5B6b5E171d78dFc947e",
        "eth",
        "Crypto.com",
        AddressType.HOT_WALLET,
        0.85,
        "etherscan",
    ),
]


def load_curated_vasp_directory() -> VASPRepository:
    repo = VASPRepository()
    for name, entity_type, jurisdiction in _ENTITIES:
        repo.add_entity(
            VASPEntity(
                name=name,
                entity_type=entity_type,
                jurisdiction=jurisdiction,
            )
        )
    for address, chain, vasp_name, address_type, confidence, source in _ADDRESSES:
        repo.add_address(
            VASPAddress(
                address=address,
                chain=chain,
                vasp_name=vasp_name,
                address_type=address_type,
                source=source,
                verification_status=VerificationStatus.VERIFIED,
                confidence=confidence,
            )
        )
    return repo