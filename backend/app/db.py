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