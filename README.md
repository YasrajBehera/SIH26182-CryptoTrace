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
