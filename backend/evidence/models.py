from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    GRAPH_PROXIMITY = "graph_proximity"
    KNOWN_ADDRESS_MATCH = "known_address_match"
    TEMPORAL_CONSISTENCY = "temporal_consistency"
    TRANSACTION_FLOW = "transaction_flow"
    CLUSTER_EVIDENCE = "cluster_evidence"
    SANCTIONS_MATCH = "sanctions_match"
    ML_PREDICTION = "ml_prediction"


class Provenance(BaseModel):
    created_at: str
    created_by: str = "attribution_engine"
    method: str
    version: str = "0.1.0"
    source_type: Optional[str] = None
    model_version: Optional[str] = None
    dataset_version: Optional[str] = None


class EvidenceRecord(BaseModel):
    evidence_id: str
    attribution_id: str
    investigation_id: Optional[str] = None
    evidence_type: EvidenceType
    address: str
    chain: str
    tx_hash: Optional[str] = None
    graph_path: Optional[List[str]] = None
    source: str = "synthetic"
    timestamp: Optional[int] = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    description: str = ""
    provenance: Provenance
