"""Pydantic models for normalized blockchain transfer data."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BlockchainTransfer(BaseModel):
    """A normalized blockchain transfer suitable for cross-chain analysis."""

    transaction_hash: str = Field(..., description="Transaction hash")
    block_number: Optional[int] = Field(None, description="Block number")
    block_timestamp: Optional[datetime] = Field(None, description="Block timestamp (UTC)")
    from_address: str = Field(..., description="Lowercase sender address")
    to_address: str = Field(..., description="Lowercase receiver address")
    value: str = Field(..., description="Transfer value as string to preserve precision")
    asset: str = Field(..., description="Asset symbol (e.g. ETH, USDT)")
    category: str = Field(..., description="Transfer category (external, internal, erc20)")
    direction: str = Field(..., description="Direction relative to the queried wallet (in/out)")
    raw_contract_address: Optional[str] = Field(None, description="ERC-20 contract address for token transfers")
    raw_contract_value: Optional[str] = Field(None, description="Raw unscaled contract value for token transfers")
    chain: str = Field(..., description="Chain identifier, e.g. eth")

    def dedup_key(self) -> tuple:
        """Return a stable key used to deduplicate transfers.

        A transaction can legitimately contain multiple distinct token transfers
        (e.g. different tokens, or multiple transfers of the same token with
        different counterparties). The key therefore combines the transaction
        hash with the direction and the address pair.
        """
        return (
            self.transaction_hash,
            self.direction,
            (self.from_address or "").lower(),
            (self.to_address or "").lower(),
            (self.raw_contract_address or "").lower(),
            self.category,
            self.value,
        )


class PaginationInfo(BaseModel):
    """Pagination metadata for a transfers response."""

    max_transfers: int = Field(..., description="Maximum number of transfers returned")
    fetched: int = Field(..., description="Number of transfers actually fetched")
    truncated: bool = Field(False, description="True if the result was truncated by a limit")
    skipped: int = Field(0, description="Malformed provider records skipped")


class WalletTransfers(BaseModel):
    """Response model for a wallet's combined transfer history."""

    wallet_address: str = Field(..., description="The queried wallet address")
    chain: str = Field(..., description="Chain identifier, e.g. eth")
    transfers: list[BlockchainTransfer] = Field(default_factory=list, description="Normalized transfers")
    pagination: PaginationInfo = Field(..., description="Pagination metadata")
