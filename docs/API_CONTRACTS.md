# Initial API contracts

## Health
GET `/api/v1/health`

## Wallet transfers (Member 1)
GET `/api/v1/wallets/{address}/transfers`

Optional query params:
- `limit` (1-10000): page size.
- `offset` (>= 0): server-side pagination over the sorted held set.
- `direction` (`in`|`out`): restrict to one direction.

The response carries a `pagination` object with `total`, `offset`,
`has_next` and `has_previous` so the UI can page without loading the whole
set into React. Verified live against `0xfb74767c1ce1aada0a0e114441173b57f8c1571b`:
`?limit=5&offset=5` returns 5 rows with `total=1000`, `has_next/previous=true`.

Response:
```json
{
  "wallet_address": "0x...",
  "chain": "eth",
  "transfers": [
    {
      "transaction_hash": "0x...",
      "block_number": 123,
      "block_timestamp": "2023-01-01T00:00:00Z",
      "from_address": "0x...",
      "to_address": "0x...",
      "value": "1000",
      "asset": "USDT",
      "category": "erc20",
      "direction": "in",
      "raw_contract_address": "0x...",
      "raw_contract_value": "0x3e8",
      "chain": "eth"
    }
  ],
  "pagination": {
    "max_transfers": 1000,
    "fetched": 1,
    "truncated": false
  }
}
```

Status codes: `200` success, `400` invalid address, `502` provider/API failure
or missing API key, `500` unexpected internal error.

## Investigation

### Cases CRUD
POST `/api/v1/investigations`
GET `/api/v1/investigations`
GET `/api/v1/investigations/{case_id}`
PATCH `/api/v1/investigations/{case_id}`
DELETE `/api/v1/investigations/{case_id}`

Cases are stored in a repository (in-memory by default, PostgreSQL-backed when
configured). Reading requires `investigation.read`; mutating requires
`investigation.update`. All mutations append audit events
(`CASE_CREATE`, `CASE_UPDATE`, `CASE_DELETE`).

Create request:
```json
{
  "name": "Suspicious deposit trail",
  "primary_wallet": "0xFB74767C1ce1aadA0a0E114441173b57f8C1571b",
  "network": "eth"
}
```

### Case notes
GET `/api/v1/investigations/{case_id}/notes`
POST `/api/v1/investigations/{case_id}/notes`

Notes are analyst observations persisted with a case and scoped to it (reading a
case never exposes another case's notes). `GET` requires `investigation.read`,
`POST` requires `investigation.update`. Audit events: `CASE_NOTE_LIST`,
`CASE_NOTE_CREATE`.

POST request:
```json
{
  "body": "Trail observed: 12-hop sweep into mixer contract.",
  "author": "Admin"
}
```

POST response (201):
```json
{
  "id": "note-0fa1c2b3",
  "case_id": "CT-2026-0142",
  "author": "Admin",
  "body": "Trail observed: 12-hop sweep into mixer contract.",
  "created_at": "2026-09-13T09:00:00Z"
}
```

GET response:
```json
{
  "case_id": "CT-2026-0142",
  "total": 2,
  "notes": [ { "id": "note-0fa1c2b3", "case_id": "CT-2026-0142", "author": "Admin", "body": "…", "created_at": "…" } ]
}
```

### Investigator Assistant (rule-based)
GET `/api/v1/assistant/quick-actions`
POST `/api/v1/assistant/query`

A deterministic, evidence-grounded assistant (no LLM). The router requires
`investigation.read`; every query is audited (`ASSISTANT_QUERY`). All responses
carry `human_review_required: true` and derive `data_source` (`live`/`synthetic`)
from the underlying evidence — never assumed. Referrals are draft-only with
`submission_state: "requires_sahyog_connection"`.

Quick actions request example:
```json
{ "case_id": "CT-2026-0142" }
```

Query request:
```json
{
  "case_id": "CT-2026-0142",
  "scope": "case",
  "intent": "summary",
  "text": "Summarize the risk in this case"
}
```

Query response (abridged):
```json
{
  "case_id": "CT-2026-0142",
  "intent": "summary",
  "human_review_required": true,
  "data_source": "mixed",
  "sections": [ { "heading": "Overview", "content": "…", "kind": "paragraph" } ],
  "referral": null
}
```

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
  ],
  "edges": [
    {
      "source": "eth:0xaaa",
      "target": "eth:0xbbb",
      "tx_id": "eth:0xabc",
      "tx_hash": "0xabc",
      "chain": "eth",
      "amount": "1000000000000000000",
      "timestamp": 1700001234,
      "block_number": 20698121
    }
  ]
}
```

Each edge carries the recorded on-chain `block_number` of the transfer when the
graph engine has it; otherwise the field is `null`.

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
