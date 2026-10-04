# 🔍 CryptoTrace

### Smart India Hackathon 2026 • Problem Statement 26182

> **Automated Attribution of Unknown Cryptocurrency Wallets to Nearest Virtual Asset Service Providers through Blockchain Intelligence APIs**

**Unknown Wallet → Blockchain Transactions → Transaction Graph → VASP Candidate Ranking → Evidence → Risk → Investigation Report**

  
[🎥 Demo Video](https://youtu.be/xp3hxlscSh4)  
[🚀 Live Demo](https://innovative-presence-production-90fa.up.railway.app)
[💻 Source Code](https://github.com/YasrajBehera/SIH26182-CryptoTrace)

**Team:** The Dynamic Innovator
## 🎥 Demo

### 🎙️ Narrated Demo
[Watch the narrated demo](https://youtu.be/xp3hxlscSh4)
## 🚀 Key Capabilities

- 🔗 **Live Ethereum Blockchain Ingestion** using Alchemy
- 🕸️ **Transaction Graph Investigation** using Neo4j and NetworkX
- 🔎 **BFS, DFS and Shortest-Path Analysis**
- 💸 **Fund-Flow Reconstruction**
- 🏢 **VASP Intelligence and Candidate Attribution**
- 🎯 **Evidence-backed deterministic attribution scoring**
- 🧾 **Evidence provenance and investigation records**
- 📋 **Persistent investigation cases and case notes**
- ⚠️ **Risk assessment and suspicious-wallet signals**
- 🤖 **Evidence-grounded Investigator Assistant**
- 📄 **Investigation report generation and PDF export**
- 🔐 **JWT authentication and role-based access control**
- 📜 **Auditable investigator activity logs**
- 🔍 **Global investigation search**
- 💰 **ETH/USD value estimation**


## 🏗️ System Architecture

text
                
                    ┌─────────────────────┐
                    │   CryptoTrace UI    │
                    │ React + TypeScript  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    FastAPI Backend  │
                    │       Render        │
                    └──────┬───────┬──────┘
                           │       │
              ┌────────────┘       └─────────────┐
              ▼                                  ▼
       ┌──────────────┐                  ┌──────────────┐
       │    Neon      │                  │ Neo4j AuraDB │
       │  PostgreSQL  │                  │    Graph     │
       └──────────────┘                  └──────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │    Alchemy   │
                    │ Ethereum API │
                    └──────────────┘
## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript, Tailwind CSS |
| Backend | Python, FastAPI |
| Blockchain | Ethereum, Alchemy |
| Graph | Neo4j, NetworkX |
| Database | PostgreSQL |
| Attribution | Deterministic scoring engine |
| ML Signal | LightGBM / Elliptic2 |
| Authentication | JWT + RBAC |
| Reports | PDF generation |
| Deployment | Railway |

## 🧪 Testing

The repository includes automated backend and frontend test suites covering core investigation, attribution, graph, evidence, API, and UI functionality.

The current repository documents:

- **498 backend tests passing**
- **94 frontend tests passing**
- Frontend typecheck/build validation
- Lint validation




## ⚠️ Data & Prototype Transparency

CryptoTrace clearly distinguishes between live and demonstration data.

- **Live blockchain ingestion:** Ethereum transaction data through Alchemy.
- **Graph analysis:** Neo4j-backed transaction relationship analysis.
- **VASP attribution:** Current prototype uses a deterministic analytical scoring approach.
- **VASP intelligence dataset:** Synthetic/demo intelligence is used where real-world ownership validation is unavailable.
- **ML suspicious-wallet signal:** The current model is based on the Elliptic2 Bitcoin-focused dataset and should not be interpreted as Ethereum-validated detection.
- **SAHYOG:** Demonstrated as a draft/integration workflow and does not represent live submission to I4C/NCRP.
- **Attribution output:** Candidate rankings support investigative leads and do not establish wallet ownership.

## 🔗 Project Links

| Resource | Link |
|---|---|
| 🚀 Live Prototype | https://innovative-presence-production-90fa.up.railway.app |
| 🎥 Original Demo | https://youtu.be/P_f_5ufgG7w |
| 💻 GitHub | https://github.com/YasrajBehera/SIH26182-CryptoTrace |
| 🌐 Ethereum | https://ethereum.org |
| 🕸️ Neo4j Documentation | https://neo4j.com/docs/ |
| ⚡ Alchemy Documentation | https://www.alchemy.com/docs |



# SIH26182-CryptoTrace

Explainable cross-chain VASP attribution and blockchain investigation platform for SIH26182.

## Current milestone

Production-style end-to-end investigation demo: wallet -> normalized transfers -> live graph
(BFS/temporal/fund-flow) -> attribution candidates with explainable confidence -> evidence with
provenance and audit trail -> investigation-ready JSON and PDF reports, plus admin/RBAC, audit
logging, rate limiting and a full test suite (backend 783 passing, frontend 146 passing).

The final milestone adds:

- **Investigator Assistant (rule-based)** — a deterministic, evidence-grounded assistant that turns
  investigation data into human-reviewable summaries, risk rationales, attribution explanations,
  wallet/VASP lookups, a transaction-timeline builder and a draft-only SAHYOG referral. It is gated
  by `investigation.read`, audits every query, and is fully test-covered backend and frontend.
- **Persisted case notes** — analyst observations stored per case (`investigation_notes` table),
  ownership-scoped read/write, surfaced as the case "Notes" tab.
- **Graph edge `block_number`** — BFS/neighbor edges now expose the on-chain block number of each
  recorded transfer alongside the timestamp.
- **Chain-scoped VASP matching** — VASP addresses are matched as `(chain, address)`, so an address
  verified on Ronin is never reported as a VASP on Ethereum and an Ethereum exchange is never
  offered as a Ronin candidate. Wallet identity, directory lookup and graph nodes are all
  chain-qualified. See "VASP directory: matching is per `(chain, address)`".
- **A verified Ronin VASP entry** — Bitget's Ronin address, verified against a real explorer
  transaction, with the transaction hash, block, source URL and evidence note carried through to the
  evidence record. A wallet is attributed to Bitget only when it is that address or an ingested
  transaction shows a real transfer; unrelated Ronin wallets return `UNKNOWN` rather than a lone
  low-score Bitget row.
- **Traceable evidence** — evidence records now carry `matched_address`, the observed `tx_hash`,
  value/asset/direction in the description, and per-record `limitations` rendered verbatim in the
  UI. Records are created only for candidates the response shows, so the evidence API never returns
  an orphan.

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
| Cases / investigations | `GET/POST/PATCH/DELETE /api/v1/investigations` | `getDemoInvestigations()` | LIVE/REAL (in-memory/DB) |
| Case creation | `POST /api/v1/investigations` | runtime demo store | LIVE/REAL |
| Case notes | `GET/POST /api/v1/investigations/{id}/notes` | `demoNotes` | LIVE/REAL |
| Investigator Assistant | `GET /api/v1/assistant/quick-actions`, `POST /api/v1/assistant/query` | `getDemoAssistantResponse()` | LIVE/REAL (rule-based) |
| User directory (admin) | `GET/POST/PATCH/DELETE /api/v1/admin/users` | seeded records | LIVE/REAL (DB or in-memory) |
| Audit log | `GET /api/v1/audit` | demo events | LIVE/REAL |
| Reports | server-side PDF export (`POST /api/v1/reports/export`, verified 4 KB `%PDF-` stream with `X-CryptoTrace-Report-Id`/`-Sections` headers) | browser print / preview | LIVE/REAL |
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
- The **Investigator Assistant** is available from the case detail ("Assistant" tab) and the
  wallet detail page, and answers with evidence-grounded, reviewer-signed content.

## Multi-chain providers

`blockchain/` is split into a chain-agnostic provider layer and per-chain adapters.
Everything downstream (graph, intelligence, attribution, evidence, reports) consumes
only the normalized `BlockchainTransfer`, so adding a chain never touches those modules.

| Module | Responsibility |
| --- | --- |
| `blockchain/chains.py` | `ChainSpec` registry, aliases, address validation, `(chain, address)` identity |
| `blockchain/errors.py` | Typed failures: `InvalidAddressError`, `UnsupportedChainError`, `ProviderNotConfiguredError`, `LiveDataUnavailableError`, `ProviderRateLimitError`, `ProviderTimeoutError`, `ProviderResponseError` |
| `blockchain/providers.py` | `BlockchainProvider` interface + `ProviderResult` provenance (`status`, `provider`, `limitations`) |
| `blockchain/registry.py` | chain id -> provider factory, plus an operator-facing configuration snapshot |
| `blockchain/ethereum_provider.py` | Adapter over the existing `AlchemyClient` / `BlockchainService` |
| `blockchain/ronin_provider.py` | Ronin via Alchemy's Ronin network, or the official public JSON-RPC |

Supported chains: `eth`, `ronin` (aliases such as `ronin-mainnet` are accepted).
Recognised-but-unimplemented chains (`bsc`, `polygon`, `solana`, `tron`) raise
`UnsupportedChainError` rather than being silently treated as Ethereum — a `0x` prefix
only proves an address is EVM-shaped, never which network it belongs to. Wallet identity
is chain-qualified (`eth:0xabc…` ≠ `ronin:0xabc…`).

`GET /api/v1/investigations/chains` returns the supported chains, their aliases and which
transports are actually configured.

### Ronin data sources

Ronin publishes **no first-party REST history API** for arbitrary addresses
(`Ronin.Rest` was retired in 2023), so two real transports are implemented:

1. **Official public JSON-RPC** — `https://api.roninchain.com/rpc` (chain id `2020`).
   No key required. Uses `eth_getLogs` over a bounded, recent block window. Ronin's
   `eth_getLogs` does return `transactionHash`, so logs are mapped to real transaction
   hashes directly; block/receipt reads are used only as a fallback for logs that omit
   it. The window is walked **newest-first in 200-block chunks** and stops as soon as
   enough transfers are found, so an active wallet resolves immediately instead of after
   the whole window.

   *Measured limits of the public endpoint:*
   - `eth_getLogs` rejects any range wider than **exactly 200 blocks**, so a wider window
     must be chunked rather than sent as one request.
   - Ronin blocks average ~2s, so 200 blocks is only **~7 minutes** of history. The
     default window is `RONIN_SCAN_BLOCKS=100000` (~2 days) bounded by
     `RONIN_MAX_REQUESTS` calls.
   - The endpoint throttles aggressively and **answers a throttled `eth_getLogs` with an
     empty result instead of an error**, which is indistinguishable from "no activity".
     An empty scan is therefore validated against a positive control (a real log from an
     unfiltered query is re-queried with the same filter form); if that control fails,
     the result is reported as *not trustworthy* rather than as `NO_DATA`.
   - 4+ concurrent calls make it hang until the request timeout, so concurrency defaults
     to 2. Point `RONIN_RPC_URL` at your own node to raise it.
   - `Transfer` encodes the sender in `topic1` and the recipient in `topic2`, so the
     wallet is matched in **both** positions; missing `topic2` silently drops every
     incoming transfer.
   - Native RON transfers emit no log and cost one block fetch per block, so they are
     scanned over their own `RONIN_NATIVE_SCAN_BLOCKS` window.

   Results are therefore reported as **`LIVE_PARTIAL`** with the exact scanned block
   range, never as complete history, and every budget is bounded so a slow or throttled
   public endpoint degrades into a disclosed partial answer instead of failing or
   reporting a false `NO_DATA`.
2. **Alchemy's Ronin network** — `https://ronin-mainnet.g.alchemy.com/v2/{key}`.
   Serves `alchemy_getAssetTransfers` and is the only transport that can return full
   Ronin history. It requires the `RONIN_MAINNET` network to be enabled for the Alchemy
   app; if it is not, the failure is reported explicitly and the provider falls back to
   the official RPC.

Transaction hashes are never invented: an event that cannot be mapped to a real hash is
excluded and counted in `limitations`.

### Live vs demo vs unavailable

`POST /api/v1/investigations/{address}/analyze` accepts an explicit `mode`:

| `mode` | Behaviour |
| --- | --- |
| `live` | Real chain data only. A provider failure is an HTTP error — synthetic data is never substituted. |
| `demo` | Synthetic transactions only; no provider is called. Always labelled `DEMO`. |
| `auto` (default) | Real data when the provider has any. Otherwise synthetic data that is explicitly labelled, with the live outcome reported in `status`, `live_status` and `limitations`. |

Only real chain data is ever written to the wallet store or mirrored into Neo4j.

Investigation statuses: `LIVE`, `LIVE_PARTIAL`, `NO_DATA` (the provider answered and
genuinely found nothing), `DEMO`. Failures map to accurate HTTP codes instead of a
generic error: `400` invalid address / unsupported chain, `429` provider rate limit,
`503` provider not configured or unavailable, `504` provider timeout.

## VASP directory: matching is per `(chain, address)`

`intelligence/curated_directory.py` holds the curated **public** VASP address directory used by
LIVE investigations. Nothing in `attribution/`, `graph/` or the UI special-cases an entry, a wallet
or a chain: the same code serves Ethereum and Ronin.

**`(chain, address)` is the identity of a match.** The same 20-byte hex string on two EVM chains is
two unrelated accounts, so an entry is only ever looked up as a pair. Consequences:

- `get_vasp_names_for_chain("ronin")` returns only VASPs that have a verified address *on Ronin*.
  A chain with no directory entry yields no candidates at all, and says so.
- A Ronin wallet is never offered an Ethereum exchange as a candidate, and the Bitget Ronin
  address is not a known VASP on Ethereum.
- Wallet identity is chain-qualified (`wallet_id("ronin", a) != wallet_id("eth", a)`), and addresses
  are normalized (trimmed, lowercased) before every lookup, so case and whitespace variants resolve
  to the same entry.
- Graph nodes are keyed `ronin:0x…`, which is what stops a verified address from being counted as
  graph proximity to a wallet on another chain.

### Verified entries

Every entry in the curated directory is `verified`, and each records the public artefact the label
was checked against: `source`, `source_url`, a plain-language `evidence` note, and
`verification_tx_hash` / `verification_block`.

| Entity | Chain | Address | Source |
| --- | --- | --- | --- |
| Bitget | `ronin` | `0x5bdf85216ec1e38D6458C870992A69e38e03F7Ef` | [ronin official explorer](https://explorer.roninchain.com/) |

The Bitget label was verified against explorer transaction
`0x733fc397a5a565a5f4ee16f15f420640a1a77982a87f12145634abf3e41ca8b2` in block `61673529`
(a real transfer of `2770.209067089073 RON` to that address). Re-checked against the live Ronin
RPC (chain id `2020`): `eth_getTransactionByHash` for that hash returns `to` = the Bitget address
in that block, so a reviewer can reproduce the label with one call.

> **That verification transaction attests the label only.** It proves the address is an active,
> explorer-labelled account; it is *not* evidence that any investigated wallet ever transacted with
> Bitget. A wallet is only attributed to Bitget when it either **is** that address on Ronin, or an
> **actually ingested** transaction shows it sending to or receiving from that address on Ronin.

### From a match to evidence

Attribution scores are unchanged (`HIGH` >= 70, `MEDIUM` >= 40) — the traceability work adds detail
to the records, not points to the score. For a match, each evidence record now carries:

- `matched_address` — the VASP-controlled address that actually matched, on `chain`;
- `tx_hash` + `timestamp` — the real transaction, clickable back to the chain;
- a description naming entity, chain, matched address, direction, value and asset, the transaction
  hash, the directory source and the graph path;
- `limitations` — what the record does **not** establish.

Two honesty rules the implementation enforces:

1. **Evidence is minted only for candidates the response actually shows.** Records are created
   after the relevance filter, so the evidence API can never return an orphan describing a finding
   the caller was not shown.
2. **A behavioural score is not a VASP-specific signal.** Temporal regularity and counterparty
   counts describe the wallet, not the (wallet, VASP) pair, so a candidate is surfaced only when the
   wallet is that VASP's directory address on this chain or an observed transaction with it exists.
   Otherwise the response returns an explicit `UNKNOWN` / score `0` placeholder instead of a lone,
   confident-looking row for a VASP the wallet has never touched. A behavioural component's evidence
   record says so in its own `limitations`.

Every attribution evidence record carries: *"A public directory label is an investigative lead. It
does not by itself establish legal ownership, control, or the identity of the operator."*
The UI renders these limitations verbatim under **"What this evidence does NOT establish"**, and
candidate cards show the chain they were analysed on instead of assuming Ethereum.

> Attribution identifies investigative leads based on available blockchain and intelligence
> evidence. It does not by itself establish legal ownership or identity.

## Honest status vocabulary

The UI never claims a feature is live when it is not. Labels used:

- **LIVE / REAL** — served by a reachable backend endpoint.
- **LIVE_PARTIAL** — real chain data that is knowingly incomplete (e.g. Ronin via the
  official RPC window).
- **NO_DATA** — a provider answered and found no activity for that wallet **within the
  range it actually searched**. It is a statement about the scanned block range (always
  disclosed in `limitations`), never a claim that the wallet is inactive, and never a
  substitute for missing data. It is only used when the search was *complete* for the
  window it claims **and** the filters were proven to work: the public Ronin RPC answers
  a throttled `eth_getLogs` with an empty list rather than an error, so every empty
  result is validated against a positive control (a real log found by an unfiltered
  query is re-queried with the same filter form). If the scan was cut short, or the
  control query also came back empty — which cannot be told apart from throttling —
  the result is `LIVE_PARTIAL` with zero transfers plus an explicit note that the empty
  result could not be validated. The UI derives confidence from the backend's threshold
  (`HIGH` >= 70, `MEDIUM` >= 40) and never raises a badge on its own.
- **DEMO / SYNTHETIC** — labeled synthetic data (fallback or on-demand pipeline over synthetic transactions).
- **NOT CONFIGURED** — feature genuinely needs a backend that is not implemented
  (server-side PDF export), or a chain provider has no credentials.
- **UNAVAILABLE / ERROR** — endpoint reachable concept exists but the provider/engine is down (e.g. Neo4j disconnected: graph shows a "Synthetic fallback — Neo4j unavailable" badge).

## Docs

- `docs/ARCHITECTURE.md` — high-level architecture
- `docs/API_CONTRACTS.md` — API contracts (cases, notes, assistant, graph engine)
- `docs/GRAPH_ENGINE.md` — Graph & Transaction Analysis module
- `docs/SCORING_METHOD.md` — attribution scoring methodology
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

Copy `.env.example` to `backend/.env` (already ignored by git) and set:

- `ALCHEMY_API_KEY` - your Alchemy Ethereum mainnet API key (never commit this).
- `RONIN_RPC_ENABLED` / `RONIN_RPC_URL` / `RONIN_SCAN_BLOCKS` / `RONIN_MAX_REQUESTS` /
  `RONIN_NATIVE_SCAN_BLOCKS` / `RONIN_RPC_CONCURRENCY` / `RONIN_CHAIN_ID` - optional
  Ronin official-RPC tuning (see "Ronin data sources").
- `RONIN_ALCHEMY_API_KEY` - optional Alchemy key with `RONIN_MAINNET` enabled, for full
  Ronin history.

If `ALCHEMY_API_KEY` is missing, a strict `mode=live` investigation returns a clear
`503` `NOT_CONFIGURED` response instead of fabricated data. The rest of the
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
npm test          # vitest suite (94 tests)
npm run lint      # eslint src --max-warnings 0
npm run build     # tsc -b && vite build
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
