# SIH26182-CryptoTrace

Explainable cross-chain VASP attribution and blockchain investigation platform for SIH26182.

## Current milestone

Wallet address -> API -> normalized transaction placeholder -> investigation-ready JSON response.

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
