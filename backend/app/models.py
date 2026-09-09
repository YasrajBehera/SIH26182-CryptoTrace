from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("chain", "tx_hash", name="uq_transactions_chain_tx_hash"),
        Index("ix_transactions_chain_from", "chain", "from_address"),
        Index("ix_transactions_chain_to", "chain", "to_address"),
        Index("ix_transactions_chain_timestamp", "chain", "block_timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tx_hash: Mapped[str] = mapped_column(String(66))
    chain: Mapped[str] = mapped_column(String(32))
    block_number: Mapped[int] = mapped_column(BigInteger)
    block_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    from_address: Mapped[str] = mapped_column(String(42))
    to_address: Mapped[str] = mapped_column(String(42))
    value: Mapped[Decimal] = mapped_column(Numeric(78, 0))
    fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(78, 0), nullable=True)
    token_symbol: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )