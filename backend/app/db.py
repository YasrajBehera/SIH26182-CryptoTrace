from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


# Bounded connect timeout so the reachability probe fails fast instead of
# hanging when a port is open but no Postgres answers (proxies/firewalls).
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5},
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

_database_available: bool | None = None


def database_available() -> bool:
    """Probe whether Postgres is reachable (cached per process).

    The repositories use this to choose a durable SQLAlchemy backend versus
    the in-memory fallback so the app keeps working offline (tests/demos)
    while staying honest about the source of records.
    """
    global _database_available
    if _database_available is not None:
        return _database_available
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        _database_available = True
    except Exception:
        _database_available = False
    return _database_available


def ensure_database_tables() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(engine)
    _migrate_investigations()
    _migrate_investigation_notes()
    _migrate_audit_result_width()
    _migrate_token_symbol_width()
    _migrate_numeric_precision()
    _migrate_risk_criminal_intelligence()
    _migrate_risk_ml_assessment()


def _migrate_investigation_notes() -> None:
    """Create the notes table on databases provisioned before it existed.

    ``create_all`` already handles fresh databases; this covers the upgrade
    path. Idempotent and tolerant of an unreachable database (repositories
    fall back to memory in that case).
    """
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS investigation_notes ("
                    "id VARCHAR(64) PRIMARY KEY, "
                    "case_id VARCHAR(64) NOT NULL, "
                    "author VARCHAR(128) NOT NULL, "
                    "body TEXT NOT NULL, "
                    "created_at TIMESTAMPTZ DEFAULT now())"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_investigation_notes_case "
                    "ON investigation_notes (case_id)"
                )
            )
    except Exception:
        # Fresh tables just created above already contain the columns; ignore
        # any race or dialect limitation.
        return


def _migrate_audit_result_width() -> None:
    """Widen the audit result column for composed verdict strings.

    ``result`` originally fit short tokens such as ``live:50``, but the
    assistant and report routes compose longer values (e.g.
    ``prepare_referral:unavailable`` or ``13:<case_id>``) which exceeded the
    original ``VARCHAR(16)`` and surfaced as a 500. ``ALTER COLUMN TYPE`` is
    idempotent so repeated startups are safe; an unreachable database is
    tolerated (repositories fall back to memory).
    """
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE audit_logs "
                    "ALTER COLUMN result TYPE VARCHAR(255)"
                )
            )
    except Exception:
        return


def _migrate_token_symbol_width() -> None:
    """Widen the transaction ``token_symbol`` column.

    ``token_symbol`` was originally ``VARCHAR(16)``. Real Ethereum chain data can
    carry arbitrarily long asset labels (notably phishing ``asset`` names such as
    ``'Visit LiquidETH.network to claim rewards'``). On live ingestion those rows
    violated the 16-char limit and ``store_transactions`` raised
    ``StringDataRightTruncation`` on commit, surfacing as a 500 on
    ``GET /api/v1/wallets/{address}/transfers``. ``ALTER COLUMN TYPE`` is
    idempotent so repeated startups are safe; an unreachable database is
    tolerated (repositories fall back to memory).
    """
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE transactions "
                    "ALTER COLUMN token_symbol TYPE VARCHAR(255)"
                )
            )
    except Exception:
        return


def _migrate_numeric_precision() -> None:
    """Widen lossy ``NUMERIC(78, 0)`` columns to 18 decimal places.

    Real Ethereum values are fractional (e.g. ``0.0000369`` ETH). With a scale of
    ``0`` those values were silently truncated/rounded during live persistence
    (``12595.3`` became ``12595``, tiny transfers became ``0``), corrupting the
    ``value`` / ``fee`` / volume fields the API and graph rely on.
    """
    target = {
        "transactions": ["value", "fee"],
        "wallets": ["incoming_volume", "outgoing_volume", "balance"],
    }
    try:
        with engine.begin() as conn:
            for table, cols in target.items():
                for col in cols:
                    conn.execute(
                        text(
                            f"ALTER TABLE {table} "
                            f"ALTER COLUMN {col} TYPE NUMERIC(78, 18)"
                        )
                    )
    except Exception:
        return


def _migrate_risk_criminal_intelligence() -> None:
    """Add the SEPARATE criminal/sanctions intelligence column to assessments.

    Pre-dates deployments of ``risk_assessments`` predating the criminal
    intelligence layer. The JSON payload is produced by the risk service from
    an exact match in the curated public intelligence directory and is kept
    entirely separate from the analytical risk score. Idempotent (``IF NOT
    EXISTS``) and tolerant of an unreachable database.
    """
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE risk_assessments "
                    "ADD COLUMN IF NOT EXISTS criminal_intelligence JSON"
                )
            )
    except Exception:
        return


def _migrate_risk_ml_assessment() -> None:
    """Add the SEPARATE ML suspicious-wallet block to risk assessments.

    Mirrors the criminal_intelligence column pattern: the ML block (probability,
    model/dataset version, top features) is stored in its own JSON column so it
    can never collide with the analytical VASP risk score. Idempotent and
    tolerant of an unreachable database.
    """
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE risk_assessments "
                    "ADD COLUMN IF NOT EXISTS ml_assessment JSON"
                )
            )
    except Exception:
        return


def _migrate_investigations() -> None:
    """Add columns introduced after the table's first deployment
    (``create_all`` never alters existing tables).

    Idempotent: relying on ``IF NOT EXISTS`` so repeated startups are safe and
    an unreachable database is tolerated (the repositories fall back to memory).
    """
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE investigations "
                    "ADD COLUMN IF NOT EXISTS latest_report_ids JSON "
                    "DEFAULT '[]'::json"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE investigations "
                    "ADD COLUMN IF NOT EXISTS evidence_count BIGINT "
                    "DEFAULT 0"
                )
            )
    except Exception:
        # Fresh tables just created above already contain the columns; ignore
        # any race or dialect limitation.
        return