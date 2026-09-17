from collections import deque
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import heapq
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from graph.db_loader import default_session_factory, load_transactions
from graph.schema import address_key


@dataclass(frozen=True)
class TransactionEdge:
    tx_hash: str
    chain: str
    sender: str
    receiver: str
    amount: Decimal
    timestamp: int


def hop_weight(edge: TransactionEdge) -> float:
    return 1.0


def amount_weight(edge: TransactionEdge) -> float:
    return float(edge.amount)


class TransactionGraph:
    def __init__(self) -> None:
        self._nodes: Dict[str, Dict] = {}
        self._out: Dict[str, List[TransactionEdge]] = {}
        self._in: Dict[str, List[TransactionEdge]] = {}
        self._edges: Dict[Tuple[str, str], TransactionEdge] = {}

    @classmethod
    def from_transactions(
        cls, transactions: Iterable["Transaction"]
    ) -> "TransactionGraph":
        graph = cls()
        for tx in transactions:
            graph.add_row(tx)
        return graph

    @classmethod
    def build(
        cls,
        db_session_factory: Optional[Callable] = None,
        batch_size: int = 1000,
    ) -> "TransactionGraph":
        factory = db_session_factory or default_session_factory
        return cls.from_transactions(load_transactions(factory, batch_size))

    def add_row(self, tx) -> None:
        chain = self._field(tx, "chain")
        tx_hash = self._field(tx, "tx_hash")
        from_address = self._field(tx, "from_address")
        to_address = self._field(tx, "to_address")
        value = self._field(tx, "value")

        if not chain or not tx_hash or not from_address or not to_address:
            return
        if value is None:
            return
        try:
            amount = value if isinstance(value, Decimal) else Decimal(value)
        except (TypeError, ValueError, InvalidOperation):
            return

        block_timestamp = self._field(tx, "block_timestamp")
        if block_timestamp is None:
            timestamp = 0
        elif isinstance(block_timestamp, int):
            timestamp = block_timestamp
        else:
            timestamp = int(block_timestamp.timestamp())
        self.add_edge(
            chain=chain,
            tx_hash=tx_hash,
            sender_address=from_address,
            receiver_address=to_address,
            amount=amount,
            timestamp=timestamp,
        )

    @staticmethod
    def _field(row, key):
        if isinstance(row, dict):
            return row.get(key)
        return getattr(row, key, None)

    def add_edge(
        self,
        chain: str,
        tx_hash: str,
        sender_address: str,
        receiver_address: str,
        amount: Decimal,
        timestamp: int,
    ) -> None:
        dedupe_key = (chain, tx_hash.lower())
        if dedupe_key in self._edges:
            return

        sender = address_key(chain, sender_address)
        receiver = address_key(chain, receiver_address)

        self._nodes.setdefault(
            sender, {"wallet_id": sender, "address": sender_address, "chain": chain}
        )
        self._nodes.setdefault(
            receiver,
            {"wallet_id": receiver, "address": receiver_address, "chain": chain},
        )

        edge = TransactionEdge(
            tx_hash=tx_hash,
            chain=chain,
            sender=sender,
            receiver=receiver,
            amount=amount,
            timestamp=int(timestamp),
        )
        self._edges[dedupe_key] = edge
        self._out.setdefault(sender, []).append(edge)
        self._in.setdefault(receiver, []).append(edge)

    @property
    def nodes(self) -> List[Dict]:
        return list(self._nodes.values())

    @property
    def edges(self) -> List[TransactionEdge]:
        return list(self._edges.values())

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    def has_node(self, wallet_id: str) -> bool:
        return wallet_id in self._nodes

    def get_edges_from(self, wallet_id: str) -> List[TransactionEdge]:
        return list(self._out.get(wallet_id, []))

    def get_edges_to(self, wallet_id: str) -> List[TransactionEdge]:
        return list(self._in.get(wallet_id, []))

    def neighbors(self, wallet_id: str) -> List[str]:
        neighbors = {
            edge.receiver for edge in self._out.get(wallet_id, [])
        }
        neighbors.update(
            edge.sender for edge in self._in.get(wallet_id, [])
        )
        return sorted(neighbors)

    def bfs_path(self, source: str, target: str) -> Dict:
        if source == target:
            return {
                "source": source,
                "destination": target,
                "path": [source] if self.has_node(source) else [],
                "hop_count": 0 if self.has_node(source) else None,
                "found": self.has_node(source),
            }
        if not self.has_node(source) or not self.has_node(target):
            return {
                "source": source,
                "destination": target,
                "path": [],
                "hop_count": None,
                "found": False,
            }

        visited = {source}
        parent: Dict[str, str] = {}
        queue: deque = deque([source])

        while queue:
            current = queue.popleft()
            if current == target:
                break
            for neighbor in self.neighbors(current):
                if neighbor not in visited:
                    visited.add(neighbor)
                    parent[neighbor] = current
                    queue.append(neighbor)

        if target not in parent:
            return {
                "source": source,
                "destination": target,
                "path": [],
                "hop_count": None,
                "found": False,
            }

        path = [target]
        node = target
        while node in parent:
            node = parent[node]
            path.append(node)
        path.reverse()

        return {
            "source": source,
            "destination": target,
            "path": path,
            "hop_count": len(path) - 1,
            "found": True,
        }

    def dfs_path(self, source: str, target: str) -> Dict:
        if source == target:
            return {
                "source": source,
                "destination": target,
                "path": [source] if self.has_node(source) else [],
                "hop_count": 0 if self.has_node(source) else None,
                "found": self.has_node(source),
            }
        if not self.has_node(source) or not self.has_node(target):
            return {
                "source": source,
                "destination": target,
                "path": [],
                "hop_count": None,
                "found": False,
            }

        visited = {source}
        stack: List[Tuple[str, List[str]]] = [(source, [source])]

        while stack:
            current, path = stack.pop()
            if current == target:
                return {
                    "source": source,
                    "destination": target,
                    "path": path,
                    "hop_count": len(path) - 1,
                    "found": True,
                }
            for neighbor in reversed(self.neighbors(current)):
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append((neighbor, path + [neighbor]))

        return {
            "source": source,
            "destination": target,
            "path": [],
            "hop_count": None,
            "found": False,
        }

    def shortest_path(self, source: str, target: str) -> Dict:
        result = self.bfs_path(source, target)
        return {
            "source": result["source"],
            "destination": result["destination"],
            "path": result["path"],
            "hop_count": result["hop_count"],
            "path_exists": result["found"],
        }

    def _weighted_neighbors(
        self, wallet_id: str, weight_fn: Callable[[TransactionEdge], float]
    ) -> List[Tuple[str, float]]:
        results: List[Tuple[str, float]] = []
        for edge in self._out.get(wallet_id, []):
            results.append((edge.receiver, weight_fn(edge)))
        for edge in self._in.get(wallet_id, []):
            results.append((edge.sender, weight_fn(edge)))
        return results

    def weighted_path(
        self,
        source: str,
        target: str,
        weight_fn: Callable[[TransactionEdge], float] = hop_weight,
    ) -> Dict:
        if source == target:
            return {
                "source": source,
                "destination": target,
                "path": [source] if self.has_node(source) else [],
                "total_cost": 0.0 if self.has_node(source) else None,
                "hop_count": 0 if self.has_node(source) else None,
                "path_exists": self.has_node(source),
            }
        if not self.has_node(source) or not self.has_node(target):
            return {
                "source": source,
                "destination": target,
                "path": [],
                "total_cost": None,
                "hop_count": None,
                "path_exists": False,
            }

        dist: Dict[str, float] = {source: 0.0}
        parent: Dict[str, str] = {}
        heap: list = [(0.0, source)]
        visited: set = set()

        while heap:
            cost, current = heapq.heappop(heap)
            if current in visited:
                continue
            visited.add(current)
            if current == target:
                break
            for neighbor, edge_cost in self._weighted_neighbors(
                current, weight_fn
            ):
                if neighbor not in visited:
                    new_cost = cost + edge_cost
                    if new_cost < dist.get(neighbor, float("inf")):
                        dist[neighbor] = new_cost
                        parent[neighbor] = current
                        heapq.heappush(heap, (new_cost, neighbor))

        if target not in parent:
            return {
                "source": source,
                "destination": target,
                "path": [],
                "total_cost": None,
                "hop_count": None,
                "path_exists": False,
            }

        path = [target]
        node = target
        while node in parent:
            node = parent[node]
            path.append(node)
        path.reverse()

        return {
            "source": source,
            "destination": target,
            "path": path,
            "total_cost": dist[target],
            "hop_count": len(path) - 1,
            "path_exists": True,
        }

    def to_dict(self) -> Dict:
        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "nodes": sorted(self.nodes, key=lambda node: node["wallet_id"]),
            "edges": [
                {
                    "tx_hash": edge.tx_hash,
                    "chain": edge.chain,
                    "sender": edge.sender,
                    "receiver": edge.receiver,
                    "amount": str(edge.amount),
                    "timestamp": edge.timestamp,
                }
                for edge in self.edges
            ],
        }