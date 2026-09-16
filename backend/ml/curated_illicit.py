"""Curated PUBLIC reference sets used by the ML ``risk/intelligence`` features.

These are the ONLY sets the live feature extractor uses to compute
``illicit_counterparty_exposure``, ``illicit_exposure_volume_ratio``,
``mixer_exposure`` and ``sanctions_exact_match``. They are deliberately small,
conservative and fully provenance-tracked — exactly like the curated sanctions
directory used by the risk service (``intelligence.curated_sanctions``):

* a counterparty is "illicit-exposed" only when its FULL address matches a
  curated public sanctions/illicit record,
* a counterparty is "mixer-exposed" only when it matches a publicly documented
  mixer/router contract listed here,
* the direct ``sanctions_exact_match`` feature re-uses the same curated
  sanctions directory as the criminal-intelligence block in the risk service,
  so the two signals never contradict each other,
* absence of a match means UNKNOWN / NOT ASSESSED — never "lawful".

Public references (as published):
  - Tornado Cash router/commiter contracts: widely reproduced public contract
    addresses (e.g. Etherscan verified contracts); Tornado Cash was sanctioned
    by OFAC on 2022-08-08.
"""

from __future__ import annotations

from typing import Dict, Tuple

# (chain, address, label, source_type, reference, notes)
_MIXER_RECORDS: Tuple[tuple, ...] = (
    (
        "eth",
        "0xd90e2f925e726aadc3f4c8c1caf790df7117b203",
        "Tornado Cash ETH Router",
        "public_documentation",
        "https://etherscan.io/address/0xd90e2f925e726aadc3f4c8c1caf790df7117b203",
        "Previously sanctioned mixer router (OFAC). Public documented contract.",
    ),
    (
        "eth",
        "0x12d66f87a04a9e220743712ce6d9bb1b5616b8fc",
        "Tornado Cash ETH Router (new)",
        "public_documentation",
        "https://etherscan.io/address/0x12d66f87a04a9e220743712ce6d9bb1b5616b8fc",
        "Public documented mixer router.",
    ),
    (
        "eth",
        "0x910cbd523d972eb0a6f4cae461dead263708c054",
        "Tornado Cash ETH Router (old)",
        "public_documentation",
        "https://etherscan.io/address/0x910cbd523d972eb0a6f4cae461dead263708c054",
        "Public documented mixer router.",
    ),
)


def load_curated_mixers() -> Dict[Tuple[str, str], dict]:
    """Return {(chain, address): record} for the curated public mixer set."""
    return {(chain, address.lower()): dict(
        chain=chain,
        address=address.lower(),
        label=label,
        source_type=source_type,
        reference=reference,
        notes=notes,
    ) for (chain, address, label, source_type, reference, notes) in _MIXER_RECORDS}


def load_curated_illicit_addresses() -> Dict[Tuple[str, str], dict]:
    """Return {(chain, address): record} for curated public sanctions records.

    Sources the SAME directory the risk service's criminal-intelligence block
    reads, so the ML ``sanctions_exact_match`` feature can never disagree with
    the separate criminal/sanctions intelligence signal.
    """
    from intelligence.curated_sanctions import load_curated_sanctions_directory

    repo = load_curated_sanctions_directory()
    out: Dict[Tuple[str, str], dict] = {}
    for record in repo.all_records():
        out[(record.chain, record.address.lower())] = {
            "entity": record.entity,
            "source": record.source,
            "source_type": record.source_type,
            "reference": getattr(record, "reference", None),
        }
    return out