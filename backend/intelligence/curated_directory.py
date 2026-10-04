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
  - Ronin official block explorer (https://explorer.roninchain.com/) public
    address labels
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
    ("Bitget", "exchange", "SG"),
]

#: The one verified Ronin VASP address, with the public artefact it was checked
#: against. Every field here is reproducible by a reviewer opening the explorer:
#: the address page carries the "Bitget 5" label and links to bitget.com, and the
#: recorded transaction is a successful, non-trivial RON transfer involving that
#: labelled address. Re-checked against the live Ronin RPC (chain id 2020):
#: eth_getTransactionByHash for that hash returns ``to`` = this address in block
#: 61673529 for 2770.209067089073 RON from 0xfef6a5e5...06a49.
#: No other Ronin VASP address is claimed, because no other one has been verified
#: the same way. This attests the LABEL only: it is never evidence that any
#: investigated wallet transacted with this address.
BITGET_RONIN = VASPAddress(
    address="0x5bdf85216ec1e38D6458C870992A69e38e03F7Ef",
    chain="ronin",
    vasp_name="Bitget",
    address_type=AddressType.DEPOSIT,
    source="ronin official explorer",
    verification_status=VerificationStatus.VERIFIED,
    confidence=0.90,
    source_url="https://explorer.roninchain.com/",
    evidence=(
        "Official Ronin explorer labels the address as Bitget 5 and the "
        "verified transaction demonstrates real activity involving the "
        "labeled address: a transfer of 2770.209067089073 RON to this address "
        "in block 61673529."
    ),
    verification_tx_hash=(
        "0x733fc397a5a565a5f4ee16f15f420640a1a77982a87f12145634abf3e41ca8b2"
    ),
    verification_block=61_673_529,
)

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
    # Verified Ronin coverage is added separately, and carries the full
    # provenance of its verification. It is deliberately NOT mirrored on
    # Ethereum: the same hex string is a different (and here unverified)
    # account on mainnet.
    repo.add_address(BITGET_RONIN)
    return repo