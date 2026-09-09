# Graph & Transaction Analysis Module

Graph engine for CryptoTrace: it reconstructs the transaction graph from the
shared PostgreSQL `transactions` table and runs path/temporal-analysis
algorithms to trace funds between wallets.

All wallet identifiers use the format `chain:address` (lowercased), e.g.
`eth:0xabc...`.

## 1. Purpose

Support blockchain investigations by answering questions such as:

- Is wallet A connected to wallet B, and through which wallets?
- What is the shortest path between two wallets?
- What is the cheapest path when edges are weighted by transfer amount?
- Which transactions moved value along a path, and in what order?
- How did funds flow from a suspicious wallet to a destination wallet?

## 2. Graph architecture

| File | Responsibility |
| --- | --- |
| `graph/builder.py` | `TransactionGraph` (in-memory graph + BFS/DFS/shortest/weighted algorithms) and `TransactionEdge` |
| `graph/db_loader.py` | PostgreSQL access (`load_transactions`, `GraphLoadError`) |
| `graph/temporal.py` | temporal-path validation and fund-flow reconstruction |
| `graph/service.py` | service functions that build the graph and delegate to the algorithms (Neo4j queries share this module) |
| `graph/api.py` | FastAPI router, prefix `/api/v1/graph`, mounted in `app/main.py` |
| `graph/schemas.py` | Pydantic request/response models |
| `graph/schema.py` | Neo4j labels, `address_key`/`transaction_key` helpers |
| `graph/synthetic.py` | synthetic transaction generator for tests |

The in-memory graph is rebuilt on every analysis from the `transactions` table
(streamed with `yield_per`); the relational database remains the single source
of truth and nothing is duplicated into storage.

## 3. Node representation

Wallets are nodes. The node id is `chain:address` (lowercased), produced by
`graph.schema.address_key(chain, address)`. Each node stores:

```python
{"wallet_id": "eth:0xabc...", "address": "0xabc...", "chain": "eth"}
```

Exposed via `graph.node_count`, `graph.nodes`, and `graph.has_node(...)`.

## 4. Edge representation

Transactions are edges. `TransactionEdge` is a frozen dataclass with:

```python
TransactionEdge(tx_hash, chain, sender, receiver, amount, timestamp)
```

- `sender` / `receiver` are wallet ids (`chain:address`)
- `amount` is a `Decimal`; `timestamp` is a Unix epoch integer
- edges are deduplicated on `(chain, tx_hash.lower())`, matching the DB unique
  constraint on `transactions(chain, tx_hash)`
- traversal is **undirected**: a hop connects any two wallets that transacted

## 5. Transaction metadata

Each edge preserves the transaction's `tx_hash`, `chain`, sender/receiver
wallet ids, `amount` (serialized as a string to avoid precision loss), and
`timestamp` (Unix seconds). These fields appear in every edge/transaction
payload returned by `to_dict`, `temporal_path`, and `fund_flow`.

## 6. BFS algorithm

`TransactionGraph.bfs_path(source, target)` returns:

```python
{"source", "destination", "path", "hop_count", "found"}
```

Uses a queue + visited set over undirected neighbors. Returns the shortest
path by hop count. Handles `source == target`, missing wallets, and
disconnected components (`found: False`).

## 7. DFS algorithm

`TransactionGraph.dfs_path(source, target)` returns the same shape as BFS.
Iterative stack traversal; **does not** guarantee a shortest path.

## 8. Shortest-path analysis

`TransactionGraph.shortest_path(source, target)` is a thin adapter over BFS
that remaps `found` to `path_exists`:

```python
{"source", "destination", "path", "hop_count", "path_exists"}
```

Exposed via `GET /api/v1/graph/shortest-path-hops`. (A separate Neo4j GDS
Dijkstra variant exists at `GET /api/v1/graph/shortest-path`.)

## 9. Weighted-path analysis

`TransactionGraph.weighted_path(source, target, weight_fn)` runs Dijkstra
(`heapq`). Weights come from `graph/builder.py`:

- `hop_weight` → `1.0` per hop
- `amount_weight` → `float(amount)`

Selection is restricted to `service.WEIGHT_FUNCTIONS` (`hops` | `amount`).
Returns:

```python
{"source", "destination", "path", "total_cost", "hop_count", "path_exists"}
```

Exposed via `GET /api/v1/graph/weighted-path?weight=hops|amount`.

## 10. Temporal analysis

`graph/temporal.py` provides:

- `sort_edges_by_time(edges, descending=False)`
- `_edge_between(graph, a, b)` — earliest edge connecting two adjacent wallets
- `validate_temporal_sequence(edges)` — checks connectivity and
  non-decreasing timestamps, returns `{is_valid, temporal_valid, chain_valid, violations}`
- `temporal_path(graph, source, target)` — path via BFS, one earliest edge per
  hop, flags `is_temporally_valid`

Exposed via `GET /api/v1/graph/temporal-path`. A per-wallet Neo4j temporal
flow is available at `GET /api/v1/graph/wallets/{wallet_id}/temporal-flow`.

## 11. Fund-flow reconstruction

`graph/temporal.py::fund_flow(graph, source, target)`:

1. finds the path via BFS
2. collects **all** transactions between each consecutive pair
   (`_all_edges_between`)
3. flattens and sorts them chronologically

Returns:

```python
{
  "source", "destination",
  "wallet_path", "hop_count",
  "transactions": [{"tx_hash", "chain", "sender", "receiver", "amount", "timestamp"}],
  "found",
}
```

Exposed via `GET /api/v1/graph/fund-flow`.

## 12. PostgreSQL integration

`graph/db_loader.py` owns all database access:

- `load_transactions(db_session_factory, batch_size=1000)` queries the
  `Transaction` model (`transactions` table), ordered by `id`, streamed with
  `yield_per`, and yields the six graph-relevant fields as dicts.
- `SQLAlchemyError` is wrapped as `GraphLoadError`, surfaced by the API as
  `503` (handler in `app/main.py`).
- Graceful handling: empty database produces an empty graph; rows missing
  required fields (`chain`, `tx_hash`, `from_address`, `to_address`, `value`)
  or with a non-numeric `value` are skipped; absent `block_timestamp` defaults
  to `0`; duplicate `(chain, tx_hash)` rows are loaded once.
- `db_session_factory` is injectable so tests use fakes (`FakeDbSession`)
  instead of a live database.

## 13. API endpoints

Path-analysis `source`, `target`, and `wallet_id` must match
`^[a-z0-9]+:[a-zA-Z0-9]+$`; malformed values return `422`.

| Endpoint | Backend | Description |
| --- | --- | --- |
| `GET /api/v1/graph/health` | Neo4j | health + wallet/transaction counts |
| `GET /api/v1/graph/summary` | PostgreSQL (in-memory) | build graph, return `wallet_count` / `transaction_count` |
| `POST /api/v1/graph/sync` | PostgreSQL → Neo4j | merge transactions into Neo4j |
| `GET /api/v1/graph/wallets/{wallet_id}/neighbors` | Neo4j | depth-1 neighbors |
| `GET /api/v1/graph/wallets/{wallet_id}/bfs` | Neo4j | BFS expansion |
| `GET /api/v1/graph/wallets/{wallet_id}/dfs` | Neo4j | DFS expansion |
| `GET /api/v1/graph/shortest-path` | Neo4j (GDS) | Dijkstra path, `weight=hops\|amount` |
| `GET /api/v1/graph/bfs-path` | in-memory | BFS path `source`→`target` |
| `GET /api/v1/graph/dfs-path` | in-memory | DFS path `source`→`target` |
| `GET /api/v1/graph/shortest-path-hops` | in-memory | shortest path by hops |
| `GET /api/v1/graph/weighted-path` | in-memory | Dijkstra, `weight=hops\|amount` |
| `GET /api/v1/graph/temporal-path` | in-memory | temporally validated path |
| `GET /api/v1/graph/fund-flow` | in-memory | chronological fund flow |
| `GET /api/v1/graph/wallets/{wallet_id}/temporal-flow` | Neo4j | per-wallet in/out flows |
| `GET /api/v1/graph/clusters` | Neo4j (GDS) | wcc/louvain/leiden communities |

See `docs/API_CONTRACTS.md` for the full contract style.

## 14. Example input

```text
# BFS path
GET /api/v1/graph/bfs-path?source=eth:0x1111111111111111111111111111111111111111&target=eth:0x5555555555555555555555555555555555555555

# Weighted path by transfer amount
GET /api/v1/graph/weighted-path?source=eth:0x1111111111111111111111111111111111111111&target=eth:0x5555555555555555555555555555555555555555&weight=amount

# Fund flow
GET /api/v1/graph/fund-flow?source=eth:0x1111111111111111111111111111111111111111&target=eth:0x5555555555555555555555555555555555555555
```

Addresses above are synthetic placeholders derived from
`tests/test_investigation_e2e.py`; they do not refer to real wallets.

## 15. Example output

```json
{
  "source": "eth:0x1111111111111111111111111111111111111111",
  "destination": "eth:0x5555555555555555555555555555555555555555",
  "wallet_path": [
    "eth:0x1111111111111111111111111111111111111111",
    "eth:0x2222222222222222222222222222222222222222",
    "eth:0x3333333333333333333333333333333333333333",
    "eth:0x4444444444444444444444444444444444444444",
    "eth:0x5555555555555555555555555555555555555555"
  ],
  "hop_count": 4,
  "transactions": [
    {
      "tx_hash": "0x0000000000000000000000000000000000000000000000000000000000000001",
      "chain": "eth",
      "sender": "eth:0x1111111111111111111111111111111111111111",
      "receiver": "eth:0x2222222222222222222222222222222222222222",
      "amount": "100",
      "timestamp": 1704067300
    }
  ],
  "found": true
}
```

The in-memory analyses (`bfs-path`, `dfs-path`, `shortest-path-hops`,
`weighted-path`, `temporal-path`, `fund-flow`) return source/destination,
`path`, `hop_count` (plus `total_cost` for weighted, `transactions` for fund
flow, and `is_temporally_valid` for temporal), and a `found`/`path_exists`
flag.

## 16. How to run graph tests

From `backend/`:

```powershell
python -m pytest -q
# or
.\.venv\Scripts\python.exe -m pytest -q
```

Graph-relevant test files:

- `tests/test_graph_builder.py` — graph construction, BFS/DFS/shortest/weighted
- `tests/test_graph_service.py` — service functions and DB-backed analysis
- `tests/test_graph_api.py` — API endpoint tests
- `tests/test_temporal.py` — temporal path and fund-flow
- `tests/test_pg_loader.py` — PostgreSQL loader and error handling
- `tests/test_investigation_e2e.py` — end-to-end synthetic investigation

Use `python -m pytest tests/test_graph_api.py -q` to run a single file.