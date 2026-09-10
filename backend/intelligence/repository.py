from typing import Dict, List, Optional, Tuple

from intelligence.models import VASPEntity, VASPAddress


class VASPRepository:
    def __init__(self) -> None:
        self._entities: Dict[str, VASPEntity] = {}
        self._addresses: List[VASPAddress] = []
        self._address_index: Dict[Tuple[str, str], List[VASPAddress]] = {}
        self._name_index: Dict[str, List[VASPAddress]] = {}

    def add_entity(self, entity: VASPEntity) -> None:
        self._entities[entity.name] = entity

    def add_address(self, vasp_addr: VASPAddress) -> None:
        self._addresses.append(vasp_addr)
        key = (vasp_addr.address.lower(), vasp_addr.chain)
        self._address_index.setdefault(key, []).append(vasp_addr)
        self._name_index.setdefault(vasp_addr.vasp_name, []).append(vasp_addr)

    def lookup_by_address(
        self, address: str, chain: str
    ) -> List[VASPAddress]:
        key = (address.lower(), chain)
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
            return [
                a for a in self._addresses
                if a.chain == chain
                and a.verification_status.value == "verified"
            ]
        return [
            a for a in self._addresses
            if a.verification_status.value == "verified"
        ]

    def get_vasp_names_for_chain(self, chain: str) -> List[str]:
        return list({
            a.vasp_name
            for a in self._addresses
            if a.chain == chain
        })
