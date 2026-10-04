from typing import Dict, List, Optional, Tuple

from blockchain.chains import canonical_chain, normalize_address
from intelligence.models import VASPEntity, VASPAddress


class VASPRepository:
    """In-memory VASP reference data, indexed by ``(chain, address)``.

    Chain is part of every lookup key. An address is only ever matched together
    with the chain it was verified on, so an Ethereum entry can never satisfy a
    Ronin lookup (and vice versa) even though both are valid 20-byte hex
    strings. Chains are canonicalised on both write and read, so ``"ronin"``,
    ``"Ronin"`` and ``"ronin-mainnet"`` all address the same bucket.
    """

    def __init__(self) -> None:
        self._entities: Dict[str, VASPEntity] = {}
        self._addresses: List[VASPAddress] = []
        self._address_index: Dict[Tuple[str, str], List[VASPAddress]] = {}
        self._name_index: Dict[str, List[VASPAddress]] = {}

    def add_entity(self, entity: VASPEntity) -> None:
        self._entities[entity.name] = entity

    def add_address(self, vasp_addr: VASPAddress) -> None:
        self._addresses.append(vasp_addr)
        key = (normalize_address(vasp_addr.address), canonical_chain(vasp_addr.chain))
        self._address_index.setdefault(key, []).append(vasp_addr)
        self._name_index.setdefault(vasp_addr.vasp_name, []).append(vasp_addr)

    def lookup_by_address(
        self, address: str, chain: str
    ) -> List[VASPAddress]:
        key = (normalize_address(address), canonical_chain(chain))
        return list(self._address_index.get(key, []))

    def lookup_by_vasp_name(self, vasp_name: str) -> List[VASPAddress]:
        return list(self._name_index.get(vasp_name, []))

    def get_entity(self, name: str) -> Optional[VASPEntity]:
        return self._entities.get(name)

    def get_all_entities(self) -> List[VASPEntity]:
        return list(self._entities.values())

    def get_all_addresses(self) -> List[VASPAddress]:
        return list(self._addresses)

    def get_known_vasp_addresses(self, chain: Optional[str] = None) -> List[VASPAddress]:
        if chain:
            wanted = canonical_chain(chain)
            return [
                a for a in self._addresses
                if canonical_chain(a.chain) == wanted
                and a.verification_status.value == "verified"
            ]
        return [
            a for a in self._addresses
            if a.verification_status.value == "verified"
        ]

    def get_vasp_names_for_chain(self, chain: str) -> List[str]:
        wanted = canonical_chain(chain)
        return list({
            a.vasp_name
            for a in self._addresses
            if canonical_chain(a.chain) == wanted
        })
