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
    )


def is_neo4j_healthy(driver: Driver) -> bool:
    try:
        driver.verify_connectedness()
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