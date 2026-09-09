# CryptoTrace Architecture

```text
React UI
   |
FastAPI
   |
   +-- Blockchain Data Service ---> RPC / Blockchain APIs
   |
   +-- Graph Intelligence --------> Neo4j + graph algorithms
   |
   +-- VASP Intelligence ---------> PostgreSQL + curated address intelligence
   |
   +-- Attribution Engine --------> candidate ranking + confidence
   |
   +-- Evidence Engine -----------> provenance + audit trail
   |
   +-- Report Service ------------> investigation-ready reports
```

## Evidence principle

An attribution result must be explainable using concrete evidence such as:

- transaction hash
- block/time
- source/destination address
- path through the transaction graph
- known VASP address/cluster
- evidence source
- evidence timestamp
- confidence contribution

Do not claim that a wallet is owned by a VASP merely because it interacted with one. Use careful language such as "high-confidence transactional association" when justified.

## Graph module

The Graph Intelligence component is documented in detail in
[`docs/GRAPH_ENGINE.md`](GRAPH_ENGINE.md). It reconstructs an in-memory
transaction graph from the shared PostgreSQL `transactions` table and runs
BFS/DFS, shortest/weighted-path, temporal, and fund-flow analysis, alongside
Neo4j-backed procedures (sync, neighbors, temporal flow, clustering).
