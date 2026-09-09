"""Pagination helpers for blockchain API clients.

Enforces configurable page/transfer caps so that client code can never
download unlimited chain history or spin forever on a rogue pageKey.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MAX_PAGES = 20
DEFAULT_MAX_TRANSFERS = 1000


@dataclass
class PaginationConfig:
    """Configuration governing how many pages / transfers may be fetched."""

    max_pages: int = DEFAULT_MAX_PAGES
    max_transfers: int = DEFAULT_MAX_TRANSFERS

    def __post_init__(self) -> None:
        if self.max_pages <= 0:
            raise ValueError("max_pages must be > 0")
        if self.max_transfers <= 0:
            raise ValueError("max_transfers must be > 0")
