# CryptoTrace Architecture

```text
React UI (live or demo data source)
   |
FastAPI (backend/ app)
   |
   +-- Blockchain Data Service ---> RPC / Blockchain APIs (Member 1)
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
   |
   +-- Security Gate -------------> JWT auth, RBAC, audit log, rate limiting
```

## Data-source model

The frontend in `frontend/src/api` is the only thing that talks to the backend. Every
module (`auth.ts`, `wallets.ts`, `graph.ts`, `attribution.ts`, `investigations.ts`,
`evidence.ts`, `audit.ts`, `users.ts`, `marketdata.ts`) follows the same pattern:

1. If `isDemoMode()` (or the live backend is unreachable/disabled) return synthetic
   records from `frontend/src/mock/*` — every record tagged `isDemo: true`.
2. Otherwise call the matching FastAPI endpoint via `client.ts` (`client.get/post/patch/del`)
   and map the wire schema (see `frontend/src/api/types.ts`) onto view models.

Mode is auto-negotiated on boot: `DataSourceProvider` probes `GET /api/v1/health`; an
operator can override in Settings -> Data source. See `frontend/src/api/config.ts`.

## Single analysis context

The end-to-end workflow is driven by one analysis. `investigations.analyze(address)`
calls `POST /api/v1/investigations/{address}/analyze` (graph → VASP attribution →
evidence), stores the returned `analysis_id` in `sessionStorage`
(`cryptotrace.lastAnalysis`, helpers `getLastAnalysis`/`setLastAnalysis`), and
threads it to downstream pages:

- **EvidencePage** reads `?analysis_id=<id>` (or the last stored analysis) and calls
  `GET /api/v1/evidence/attribution/{analysis_id}`; without an id it falls back to
  `GET /api/v1/evidence/address/{address}`.
- **Dashboard** lights the workflow strip up to the last completed stage when a
  context exists.
- **InvestigationAnalyzer** (wallet explorer) links results into graph, transaction
  history, and evidence carrying the address/analysis id.

## Honest status vocabulary

Component status is never assumed. The UI distinguishes:

- **LIVE / REAL** — served by a reachable backend endpoint.
- **DEMO / SYNTHETIC** — labeled synthetic data.
- **NOT CONFIGURED** — feature has no backend implementation (case CRUD, server-side PDF).
- **UNAVAILABLE / ERROR** — engine down (e.g. Neo4j disconnected → graph page shows the
  "Synthetic fallback — Neo4j unavailable" badge, driven by `GET /api/v1/graph/health`).

### Component status matrix

| Component | Backend | Frontend status label |
| --- | --- | --- |
| Auth / RBAC / audit / users | `app/auth` + `app/graph` repos | LIVE/REAL |
| Wallet transfers | `GET /api/v1/wallets/{address}/transfers` | LIVE/REAL |
| Graph BFS/temporal/fund-flow | `postgres` TransactionGraph + Neo4j procedures | LIVE/REAL or DEMO/SYNTHETIC (health-probed) |
| Attribution | `POST /api/v1/investigations/{address}/analyze` | LIVE/REAL pipeline (synthetic txs) |
| Evidence | in-memory `EvidenceRepository` | LIVE/REAL in-process; not persisted |
| Cases CRUD | no backend | NOT CONFIGURED (demo runtime store only) |
| Reports (server PDF) | no backend | NOT CONFIGURED (browser print) |
| SAHYOG | no backend adapter | DEMO/INTEGRATION-READY |

## Security notes

- The interactive docs (`/docs`, `/openapi.json`) are served with a branded
  Content-Security-Policy that allows the Swagger UI CDN (`cdn.jsdelivr.net`);
  every API response keeps the strict `default-src 'self'; frame-ancestors 'none'`
  policy. See `app/middleware.py`.
- The token-signing secret comes from `AUTH_SECRET`. Without it, development
  generates a random secret once and persists it to a git-ignored dotfile
  (`backend/.auth_dev_secret`, 0600 on POSIX) so tokens survive backend
  restarts. The value is never logged or committed. See `app/config.py`.
- On a `401` the frontend `client.ts` discards the local token and fires a
  `cryptotrace:unauthorized` event; `AuthContext` clears a live session and
  shows the session-expired re-login modal instead of a dead error screen.

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

## Frontend feature map

- `features/wallets` — wallet transfers + fiat estimation (`TransferTable` ≈ USD column)
- `features/transactions` — transaction explorer: filters for direction, amount, asset, chain/date
- `features/graph` — GraphPage: BFS graph, temporal flow, fund-flow path (`?to=`), health-probed provider badge
- `features/vasp` + `features/risk` — VASP directory (`?entity=` filter), risk scoring, attribution candidates
- `features/investigations` — cases, evidence, reports
- `features/sahyog` — I4C referral-flow demo (permission `wallet.analyze`)
- `features/admin` — Users, Roles, Audit (JWT + RBAC protected)
- `app/DataSourceContext.tsx` — live/demo negotiation
- `api/investigations.ts` — `getLastAnalysis`/`setLastAnalysis` (session context)
