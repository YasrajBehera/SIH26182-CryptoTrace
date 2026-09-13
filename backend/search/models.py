"""Global search contracts.

Results are always data-grounded: every record returned comes from data that
was either persisted by the pipeline (cases, wallets, transactions, evidence,
analyses) or curated publicly (VASP directory) or recorded in the audit trail
(reports). Search never fabricates results.
"""

from __future__ import annotations

from typing import Dict, List, Literal

from pydantic import BaseModel, Field

SearchEntityType = Literal[
    "investigation",
    "wallet",
    "transaction",
    "evidence",
    "attribution",
    "vasp",
    "report",
]


class SearchResult(BaseModel):
    entity_type: SearchEntityType
    id: str
    title: str
    subtitle: str = ""
    url: str = ""
    source: str = "memory"
    metadata: Dict = Field(default_factory=dict)


class GlobalSearchResponse(BaseModel):
    query: str
    results: List[SearchResult] = Field(default_factory=list)
    total: int = 0
    source: str = "memory"