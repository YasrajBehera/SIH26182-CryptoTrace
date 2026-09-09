# Initial API contracts

## Health
GET `/api/v1/health`

## Investigation
POST `/api/v1/investigations`

Request:
```json
{
  "address": "PUBLIC_WALLET_ADDRESS"
}
```

Response:
```json
{
  "wallet": "PUBLIC_WALLET_ADDRESS",
  "status": "created",
  "transactions": [],
  "message": "Blockchain ingestion module is not connected yet."
}
```

These contracts will evolve as modules are implemented. Avoid changing shared contracts without discussing the change with the team.

## Graph engine (`/api/v1/graph`)

Wallet identifiers use the format `chain:address` (lowercased), e.g. `eth:0xabc...`.
Path-analysis query params (`source`/`target`) and `wallet_id` path params are validated
against this structure; malformed values return `422`. Valid chain segments are lowercase
alphanumeric and addresses are alphanumeric, e.g. `eth:0xabc`, `btc:1abc...`.

### Graph summary (build/load the in-memory transaction graph)
GET `/api/v1/graph/summary`

Builds the in-memory `TransactionGraph` from the shared `transactions` table and reports
its size.

Response:
```json
{
  "wallet_count": 123,
  "transaction_count": 456
}
```

### Graph health
GET `/api/v1/graph/health`

Response:
```json
{
  "status": "ok",
  "wallets": 123,
  "transactions": 456
}
```

### Sync transactions from PostgreSQL into Neo4j
POST `/api/v1/graph/sync`

Reads rows from the shared `transactions` table and `MERGE`s them into Neo4j as
`(:Wallet)-[:SENT]->(:Transaction)-[:RECEIVED]->(:Wallet)`.

Response:
```json
{
  "synced": 1000
}
```

### Neighbors (depth 1) and BFS
GET `/api/v1/graph/wallets/{wallet_id}/neighbors?depth=1&max_nodes=100`
GET `/api/v1/graph/wallets/{wallet_id}/bfs?depth=3&max_nodes=100`

Response:
```json
{
  "wallet_id": "eth:0xaaa",
  "max_depth": 3,
  "nodes": [
    {"wallet_id": "eth:0xbbb", "address": "0xbbb", "chain": "eth", "depth": 1}
  ]
}
```

### DFS
GET `/api/v1/graph/wallets/{wallet_id}/dfs?depth=6&max_nodes=100`

Same shape as BFS but omits `depth` on nodes.

### Shortest path
GET `/api/v1/graph/shortest-path?source=eth:0xaaa&target=eth:0xbbb&weight=hops`

`weight`: `hops` (unweighted, default) or `amount`.

Response:
```json
{
  "source": "eth:0xaaa",
  "target": "eth:0xbbb",
  "weight": "hops",
  "found": true,
  "total_cost": 2.0,
  "nodes": [
    {"node_id": 5, "label": "Wallet", "wallet_id": "eth:0xaaa", "tx_id": null, "address": "0xaaa"},
    {"node_id": 9, "label": "Transaction", "wallet_id": null, "tx_id": "eth:0xabc", "address": null}
  ]
}
```

### Temporal flow
GET `/api/v1/graph/wallets/{wallet_id}/temporal-flow?from_ts=1700000000&to_ts=1700009999&direction=all`

`direction`: `in`, `out`, or `all`. Timestamps are Unix epoch seconds.

Response:
```json
{
  "wallet_id": "eth:0xaaa",
  "direction": "all",
  "flows": [
    {
      "tx_id": "eth:0xabc",
      "tx_hash": "0xabc",
      "chain": "eth",
      "block_timestamp": 1700001234,
      "amount": "1000000000000000000",
      "source": "eth:0xaaa",
      "target": "eth:0xbbb"
    }
  ]
}
```

### Clusters (GDS community detection)
GET `/api/v1/graph/clusters?algorithm=louvain&min_community_size=2`

`algorithm`: `wcc`, `louvain` (default), or `leiden`. Requires the Graph Data
Science plugin enabled in the Neo4j container.
