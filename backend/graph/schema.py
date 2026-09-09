from typing import List

from neo4j import Driver

from graph.neo4j_client import neo4j_session

WALLET_LABEL = "Wallet"
TRANSACTION_LABEL = "Transaction"
SENT_REL = "SENT"
RECEIVED_REL = "RECEIVED"


def address_key(chain: str, address: str) -> str:
    return f"{chain}:{address.lower()}"


def transaction_key(chain: str, tx_hash: str) -> str:
    return f"{chain}:{tx_hash.lower()}"


SCHEMA_STATEMENTS: List[str] = [
    "CREATE CONSTRAINT wallet_key_uniqueness IF NOT EXISTS FOR (w:Wallet) REQUIRE w.wallet_id IS UNIQUE",
    "CREATE CONSTRAINT transaction_key_uniqueness IF NOT EXISTS FOR (t:Transaction) REQUIRE t.tx_id IS UNIQUE",
    "CREATE INDEX wallet_address_index IF NOT EXISTS FOR (w:Wallet) ON (w.address)",
    "CREATE INDEX transaction_timestamp_index IF NOT EXISTS FOR (t:Transaction) ON (t.block_timestamp)",
    "CREATE INDEX sent_timestamp_index IF NOT EXISTS FOR ()-[r:SENT]->() ON (r.timestamp)",
    "CREATE INDEX received_timestamp_index IF NOT EXISTS FOR ()-[r:RECEIVED]->() ON (r.timestamp)",
]


def ensure_schema(driver: Driver) -> None:
    with neo4j_session(driver) as session:
        for statement in SCHEMA_STATEMENTS:
            session.run(statement)