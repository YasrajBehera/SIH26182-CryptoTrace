from contextlib import contextmanager
from typing import Iterator, Optional

from neo4j import Driver, GraphDatabase, Session

from app.config import settings


def create_driver(
    uri: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Driver:
    return GraphDatabase.driver(
        uri or settings.neo4j_uri,
        auth=(username or settings.neo4j_username, password or settings.neo4j_password),
        # Bound connection attempts so graph calls / report export fail fast
        # instead of blocking for the driver's default (30-60s) when Neo4j is
        # unavailable.
        connection_timeout=5,
        connection_acquisition_timeout=5,
    )


def is_neo4j_healthy(driver: Driver) -> bool:
    try:
        # neo4j >= 6 uses verify_connectivity(); older 5.x used
        # verify_connectedness(). Try the current API first so a live driver is
        # never misreported as unhealthy, then fall back for compatibility.
        verify = getattr(driver, "verify_connectivity", None)
        if verify is None:
            verify = getattr(driver, "verify_connectedness")
        verify()
        return True
    except Exception:
        return False


@contextmanager
def neo4j_session(driver: Driver) -> Iterator[Session]:
    session = driver.session()
    try:
        yield session
    finally:
        session.close()