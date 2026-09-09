CREATE CONSTRAINT wallet_key_uniqueness IF NOT EXISTS FOR (w:Wallet) REQUIRE w.wallet_id IS UNIQUE;
CREATE CONSTRAINT transaction_key_uniqueness IF NOT EXISTS FOR (t:Transaction) REQUIRE t.tx_id IS UNIQUE;
CREATE INDEX wallet_address_index IF NOT EXISTS FOR (w:Wallet) ON (w.address);
CREATE INDEX transaction_timestamp_index IF NOT EXISTS FOR (t:Transaction) ON (t.block_timestamp);
CREATE INDEX sent_timestamp_index IF NOT EXISTS FOR ()-[r:SENT]->() ON (r.timestamp);
CREATE INDEX received_timestamp_index IF NOT EXISTS FOR ()-[r:RECEIVED]->() ON (r.timestamp);