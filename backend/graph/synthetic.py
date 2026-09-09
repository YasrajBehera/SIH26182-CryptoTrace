import random
from dataclasses import dataclass
from typing import List

_HEX = "0123456789abcdef"
_START_TIMESTAMP = 1704067200


@dataclass(frozen=True)
class SyntheticTransaction:
    chain: str
    tx_hash: str
    from_address: str
    to_address: str
    value: str
    block_timestamp: int


def _rand_hex(rng: random.Random, length: int) -> str:
    return "".join(rng.choice(_HEX) for _ in range(length))


def gen_wallet_address(rng: random.Random, chain: str) -> str:
    return "0x" + _rand_hex(rng, 40)


def generate_transactions(seed: int = 42, count: int = 20) -> List[SyntheticTransaction]:
    rng = random.Random(seed)
    chains = ["eth", "bsc"]
    networks = {
        chain: [gen_wallet_address(rng, chain) for _ in range(6)] for chain in chains
    }
    transactions: List[SyntheticTransaction] = []
    for index in range(count):
        chain = chains[index % len(chains)]
        source = rng.choice(networks[chain])
        receiver = rng.choice([w for w in networks[chain] if w != source])
        transactions.append(
            SyntheticTransaction(
                chain=chain,
                tx_hash="0x" + _rand_hex(rng, 64),
                from_address=source,
                to_address=receiver,
                value=str(rng.randint(1000, 10**21)),
                block_timestamp=_START_TIMESTAMP + index * 60,
            )
        )
    return transactions