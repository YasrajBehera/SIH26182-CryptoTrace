# SIH26182-CryptoTrace

Explainable cross-chain VASP attribution and blockchain investigation platform for SIH26182.

## Current milestone

Production-style end-to-end investigation demo: wallet -> normalized transfers -> live graph
(BFS/temporal/fund-flow) -> attribution candidates with explainable confidence -> evidence with
provenance and audit trail -> investigation-ready JSON and PDF reports, plus admin/RBAC, audit
logging, rate limiting and a full test suite (backend 334+ passing, frontend 50 passing).

## REAL vs DEMO

The frontend runs in two modes, auto-negotiated on boot by probing `GET /api/v1/health`:

- **live** — backend reachable; all reads/writes call `client.ts` (FastAPI).
- **demo** — backend unreachable or feature not yet implemented; synthetic clearly-labeled data
  (`isDemo: true`), no network calls. The UI shows a persistent DEMO DATA banner.

| Feature | Live (backend) | Demo / Synthetic fallback | Status |
| --- | --- | --- | --- |
| Auth / login / token (JWT) | `POST /api/v1/auth/login` | seeded demo matrix | LIVE/REAL |
| RBAC permissions | `GET /api/v1/admin/users/roles` | seeded matrix | LIVE/REAL |
| Wallet transfers | `GET /api/v1/wallets/{address}/transfers` | seeded data | LIVE/REAL |
| Graph BFS / temporal / fund-flow | `/api/v1/graph/wallets/{id}/bfs`, `/temporal-flow`, `/fund-flow` | `getDemoGraph()` when Neo4j unreachable | LIVE/REAL (Neo4j) or DEMO/SYNTHETIC |
| Graph health | `GET /api/v1/graph/health` | `synthetic` when probe fails | honest provider badge |
| Attribution analysis | `POST /api/v1/investigations/{address}/analyze` | `getDemoCandidates()` | LIVE/REAL (pipeline) |
| VASP names | `GET /api/v1/intelligence/vasp/names` | `getDemoVaspNames()` | LIVE/REAL |
| Evidence / provenance | `GET /api/v1/evidence/address/{a}`, `GET /api/v1/evidence/attribution/{analysis_id}` | `getDemoProvenance()` | LIVE/REAL (in-memory) |
| Cases / investigations | no CRUD endpoint (live `[]`) | `getDemoInvestigations()` | NOT CONFIGURED |
| Case creation | throws in live | runtime demo store (survives session) | DEMO only |
| User directory (admin) | `GET/POST/PATCH/DELETE /api/v1/admin/users` | seeded records | LIVE/REAL (DB or in-memory) |
| Audit log | `GET /api/v1/audit` | demo events | LIVE/REAL |
| Reports | server-side export **not implemented** | browser print / preview | NOT CONFIGURED |
| SAHYOG referral intake | no backend adapter | synthetic referrals only | DEMO/INTEGRATION-READY |
| ETH/USD fiat estimate | CoinGecko `simple/price` (1h cache) | constant `DEMO_ETH_USD = 3500` | LIVE/REAL |

Manual override: Settings -> Data source picker (`DataSourceProvider` / `setMode`).

Demo accounts use password `cryptotrace-demo` (admin, senior_investigator, investigator, analyst, reviewer, read_only).

## Single investigation flow

One investigation/analysis context threads through the whole UI. The backend
pipeline `POST /api/v1/investigations/{address}/analyze` returns an `analysis_id`;
the frontend stores it in `sessionStorage` (`cryptotrace.lastAnalysis`) so
downstream pages reuse the same address/analysis without re-entry:

`Login → Dashboard → Wallet Lookup → Transfers → Analysis (graph→VASP→evidence) → Transactions → Graph / Fund Flow → Risk → VASP Attribution → Evidence (with ?analysis_id=) → Reports → SAHYOG → Audit`

- The dashboard workflow strip lights up to the last completed stage.
- The evidence workspace reads `?analysis_id=<id>` (or the last stored analysis)
  and calls `GET /api/v1/evidence/attribution/{analysis_id}`.
- Live wallet-analysis links carry the address into graph, transactions, and evidence.

## Honest status vocabulary

The UI never claims a feature is live when it is not. Labels used:

- **LIVE / REAL** — served by a reachable backend endpoint.
- **DEMO / SYNTHETIC** — labeled synthetic data (fallback or on-demand pipeline over synthetic transactions).
- **NOT CONFIGURED** — feature genuinely needs a backend that is not implemented
  (case persistence CRUD, server-side PDF export).
- **UNAVAILABLE / ERROR** — endpoint reachable concept exists but the provider/engine is down (e.g. Neo4j disconnected: graph shows a "Synthetic fallback — Neo4j unavailable" badge).

## Docs

- `docs/ARCHITECTURE.md` — high-level architecture
- `docs/API_CONTRACTS.md` — API contracts
- `docs/GRAPH_ENGINE.md` — Graph & Transaction Analysis module
- `docs/TEAM.md` — team responsibilities

## Team branches

- feature/blockchain-ingestion
- feature/graph-engine
- feature/attribution-intelligence
- feature/frontend-security

## Stack

- Backend: Python + FastAPI
- Frontend: React + TypeScript + Vite
- Relational DB: PostgreSQL
- Graph DB: Neo4j
- Optional cache/jobs: Redis
- Blockchain providers: RPC/API adapters
- Graph analysis: NetworkX/Neo4j
- ML later: scikit-learn/XGBoost/PyTorch Geometric

## Run backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs

Notes:

- Swagger UI renders because the backend relaxes the Content-Security-Policy
  only for `/docs`/`/openapi.json` (the Swagger CDN); all API responses keep
  the strict policy.
- Without an `AUTH_SECRET` env var, development generates one random token
  secret and persists it to a git-ignored `backend/.auth_dev_secret`, so login
  tokens keep verifying after backend restarts (no more surprise `401`s). Set
  `AUTH_SECRET` in production.

## Member 1 - Blockchain data layer

The blockchain ingestion layer normalizes Ethereum transfers for a wallet so
downstream Members (graph, intelligence, attribution) can consume clean,
deduplicated, chronological data.

### Environment variables

Copy `backend/.env.example` to `backend/.env` (already ignored by git) and set:

- `ALCHEMY_API_KEY` - your Alchemy Ethereum mainnet API key (never commit this).

If `ALCHEMY_API_KEY` is missing, the wallet-transfers endpoint returns a clear
`502` "provider is unavailable or misconfigured" response. The rest of the
application keeps working.

### How the service works

`GET /api/v1/wallets/{address}/transfers` returns normalized transfers. Internally
the `blockchain` package:

1. `validators.py` - validates the Ethereum address (format + EIP-55 checksum).
2. `alchemy_client.py` - async HTTP client for `alchemy_getAssetTransfers`
   (incoming + outgoing; external, internal and ERC-20 categories) with
   timeouts, HTTP/API error handling and pagination caps.
3. `pagination.py` - configurable page/transfer limits so we never download
   unlimited chain history.
4. `service.py` - validates, fetches incoming and outgoing transfers, combines,
   deduplicates (keeping distinct token transfers in the same transaction),
   normalizes and sorts chronologically.
5. `models.py` - Pydantic response models.

### API endpoint

**`GET /api/v1/wallets/{address}/transfers`**

Optional query param `limit` (1-10000) caps the number of transfers returned.

Status codes:
- `200` - success
- `400` - invalid Ethereum address
- `502` - blockchain provider / API failure or missing API key
- `500` - unexpected internal error

Example response:

```json
{
  "wallet_address": "0x742d35cc6634c0532925a3b844bc454e4438f44e",
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

### Running tests

Unit tests are fully offline - they mock the blockchain client and never require
an Alchemy key, Postgres, Neo4j, Redis or internet access. Run from the project
root (or `backend/`):

```powershell
python -m pytest
```

## Run frontend

```powershell
cd frontend
npm install
npm run dev
```

Open the printed Vite URL (default http://127.0.0.1:5173). The app auto-detects the backend;
run both to get live data.

### Frontend checks

```powershell
npm test          # vitest suite (50 tests)
npm run lint      # eslint src --max-warnings 0
npm run build     # tsc --noEmit && vite build
```

## Git workflow

Never work directly on `main`.

```powershell
git checkout main
git pull origin main
git checkout -b feature/your-name
```

After work:

```powershell
git add .
git commit -m "Describe the change"
git push -u origin feature/your-name
```

Then open a Pull Request on GitHub.
