from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class SyncResponse(BaseModel):
    synced: int


class GraphSummary(BaseModel):
    wallet_count: int
    transaction_count: int


class GraphHealth(BaseModel):
    status: Literal["ok", "unavailable"]
    wallets: int = 0
    transactions: int = 0


class WalletSummary(BaseModel):
    wallet_id: str
    address: str
    chain: str


class Neighbor(WalletSummary):
    depth: int


class GraphEdge(BaseModel):
    source: str
    target: str
    tx_id: Optional[str] = None
    tx_hash: Optional[str] = None
    chain: Optional[str] = None
    amount: Optional[str] = None
    timestamp: Optional[int] = None


class BFSResponse(BaseModel):
    wallet_id: str
    max_depth: int
    nodes: List[Neighbor] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)


class DFSResponse(BaseModel):
    wallet_id: str
    max_depth: int
    nodes: List[WalletSummary] = Field(default_factory=list)


class PathNode(BaseModel):
    node_id: Optional[int] = None
    label: Optional[str] = None
    wallet_id: Optional[str] = None
    tx_id: Optional[str] = None
    address: Optional[str] = None


class ShortestPathResponse(BaseModel):
    source: str
    target: str
    weight: str
    found: bool
    total_cost: Optional[float] = None
    nodes: List[PathNode] = Field(default_factory=list)


class BFSPathResponse(BaseModel):
    source: str
    destination: str
    path: List[str] = Field(default_factory=list)
    hop_count: Optional[int] = None
    found: bool = False


class DFSPathResponse(BaseModel):
    source: str
    destination: str
    path: List[str] = Field(default_factory=list)
    hop_count: Optional[int] = None
    found: bool = False


class HopsShortestPathResponse(BaseModel):
    source: str
    destination: str
    path: List[str] = Field(default_factory=list)
    hop_count: Optional[int] = None
    path_exists: bool = False


class WeightedPathResponse(BaseModel):
    source: str
    destination: str
    path: List[str] = Field(default_factory=list)
    total_cost: Optional[float] = None
    hop_count: Optional[int] = None
    path_exists: bool = False


class TemporalFlowRow(BaseModel):
    tx_id: str
    tx_hash: str
    chain: str
    block_timestamp: int
    amount: str
    source: str
    target: str


class TemporalPathEdge(BaseModel):
    tx_hash: str
    chain: str
    sender: str
    receiver: str
    amount: str
    timestamp: int


class TemporalPathTransaction(BaseModel):
    tx_hash: str
    chain: str
    sender: str
    receiver: str
    amount: str
    timestamp: int

class TemporalPathResponse(BaseModel):
    source: str
    destination: str
    path: List[str] = Field(default_factory=list)
    edges: List[TemporalPathTransaction] = Field(default_factory=list)
    is_temporally_valid: bool = False
    total_hops: int = 0
    found: bool = False


class FundFlowResponse(BaseModel):
    source: str
    destination: str
    wallet_path: List[str] = Field(default_factory=list)
    hop_count: int = 0
    transactions: List[FundFlowTransaction] = Field(default_factory=list)
    found: bool = False


class FundFlowTransaction(BaseModel):

    tx_hash: str

    chain: str

    sender: str

    receiver: str

    amount: str

    timestamp: int



class TemporalFlowResponse(BaseModel):
    wallet_id: str
    direction: str
    from_ts: Optional[int] = None
    to_ts: Optional[int] = None
    flows: List[TemporalFlowRow] = Field(default_factory=list)


class Community(BaseModel):
    community_id: int
    wallets: List[WalletSummary] = Field(default_factory=list)


class ClustersResponse(BaseModel):
    algorithm: str
    communities: List[Community] = Field(default_factory=list)