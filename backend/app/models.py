from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
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
    value: Mapped[Decimal] = mapped_column(Numeric(78, 18))
    fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(78, 18), nullable=True)
    token_symbol: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        Index("ix_users_role", "role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64))
    display_name: Mapped[str] = mapped_column(String(128))
    email: Mapped[str] = mapped_column(String(254), default="")
    role: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(128), default="")
    password_hash: Mapped[str] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_active_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_timestamp", "timestamp"),
        Index("ix_audit_logs_user_action", "user", "action"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    user: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(32))
    resource: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str] = mapped_column(String(128), default="")
    result: Mapped[str] = mapped_column(String(255))
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class Investigation(Base):
    __tablename__ = "investigations"
    __table_args__ = (
        Index("ix_investigations_owner", "created_by"),
        Index("ix_investigations_status", "status"),
        Index("ix_investigations_wallet", "primary_wallet"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    primary_wallet: Mapped[str] = mapped_column(String(42))
    network: Mapped[str] = mapped_column(String(16), default="eth")
    status: Mapped[str] = mapped_column(String(32), default="open")
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    risk: Mapped[str] = mapped_column(String(16), default="unknown")
    created_by: Mapped[int] = mapped_column(BigInteger)
    assigned_analyst: Mapped[str] = mapped_column(String(128), default="Unassigned")
    latest_analysis_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    latest_data_source: Mapped[str] = mapped_column(String(32), default="demo")
    evidence_count: Mapped[int] = mapped_column(BigInteger, default=0)
    latest_transactions: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)
    latest_candidates: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)
    latest_report_ids: Mapped[List] = mapped_column(JSON, default=list)
    tags: Mapped[List] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InvestigationNote(Base):
    __tablename__ = "investigation_notes"
    __table_args__ = (
        Index("ix_investigation_notes_case", "case_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64))
    author: Mapped[str] = mapped_column(String(128))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (
        UniqueConstraint("address", "chain", name="uq_wallets_address_chain"),
        Index("ix_wallets_chain_address", "chain", "address"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str] = mapped_column(String(42))
    chain: Mapped[str] = mapped_column(String(16))
    first_seen: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_activity: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    transaction_count: Mapped[int] = mapped_column(BigInteger, default=0)
    incoming_volume: Mapped[Decimal] = mapped_column(Numeric(78, 18), default=0)
    outgoing_volume: Mapped[Decimal] = mapped_column(Numeric(78, 18), default=0)
    balance: Mapped[Optional[Decimal]] = mapped_column(Numeric(78, 18), nullable=True)
    risk: Mapped[str] = mapped_column(String(16), default="unknown")
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    investigation_status: Mapped[str] = mapped_column(String(32), default="not_analyzed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VaspEntity(Base):
    __tablename__ = "vasp_entities"
    __table_args__ = (
        UniqueConstraint("name", name="uq_vasp_entities_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    entity_type: Mapped[str] = mapped_column(String(32), default="other")
    jurisdiction: Mapped[str] = mapped_column(String(64), default="unknown")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)


class VaspAddress(Base):
    __tablename__ = "vasp_addresses"
    __table_args__ = (
        UniqueConstraint(
            "address", "chain", "vasp_name", name="uq_vasp_addresses_addr_chain_name"
        ),
        Index("ix_vasp_addresses_lookup", "address", "chain"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str] = mapped_column(String(42))
    chain: Mapped[str] = mapped_column(String(16))
    vasp_name: Mapped[str] = mapped_column(String(128))
    address_type: Mapped[str] = mapped_column(String(32), default="unknown")
    source: Mapped[str] = mapped_column(String(32), default="synthetic")
    verification_status: Mapped[str] = mapped_column(String(16), default="unverified")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)


class AttributionResult(Base):
    __tablename__ = "attribution_results"
    __table_args__ = (
        UniqueConstraint("analysis_id", name="uq_attribution_results_analysis_id"),
        Index("ix_attribution_results_address", "address", "chain"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[str] = mapped_column(String(64))
    address: Mapped[str] = mapped_column(String(42))
    chain: Mapped[str] = mapped_column(String(16))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    candidates: Mapped[List] = mapped_column(JSON, default=list)
    disclaimer: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Evidence(Base):
    __tablename__ = "evidence_records"
    __table_args__ = (
        UniqueConstraint("evidence_id", name="uq_evidence_records_evidence_id"),
        Index("ix_evidence_attribution", "attribution_id"),
        Index("ix_evidence_investigation", "investigation_id"),
        Index("ix_evidence_address", "address", "chain"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[str] = mapped_column(String(64))
    attribution_id: Mapped[str] = mapped_column(String(64))
    investigation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    evidence_type: Mapped[str] = mapped_column(String(32))
    address: Mapped[str] = mapped_column(String(42))
    chain: Mapped[str] = mapped_column(String(16))
    tx_hash: Mapped[Optional[str]] = mapped_column(String(66), nullable=True)
    graph_path: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="synthetic")
    timestamp: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    description: Mapped[str] = mapped_column(Text, default="")
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    __table_args__ = (
        Index("ix_risk_assessments_investigation", "investigation_id"),
        Index("ix_risk_assessments_wallet", "wallet_address", "chain"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    investigation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    wallet_address: Mapped[str] = mapped_column(String(42))
    chain: Mapped[str] = mapped_column(String(16))
    level: Mapped[str] = mapped_column(String(16), default="unknown")
    risk_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    summary: Mapped[str] = mapped_column(Text, default="")
    factors: Mapped[List] = mapped_column(JSON, default=list)
    criminal_intelligence: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )
    ml_assessment: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SahyogReferral(Base):
    __tablename__ = "sahyog_referrals"
    __table_args__ = (
        Index("ix_sahyog_referrals_status", "status"),
        Index("ix_sahyog_referrals_wallet", "suspect_wallet"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    fir_no: Mapped[str] = mapped_column(String(64))
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    victim_name: Mapped[str] = mapped_column(String(128))
    amount_usdt: Mapped[Decimal] = mapped_column(Numeric(24, 2))
    suspect_wallet: Mapped[str] = mapped_column(String(42))
    chain: Mapped[str] = mapped_column(String(8), default="eth")
    status: Mapped[str] = mapped_column(String(16), default="new")
    triage: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    handoff_case_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )