from pathlib import Path as _Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Path, Query
from pydantic import BaseModel, Field

# Load backend/.env into os.environ so blockchain.alchemy_client can read
# ALCHEMY_API_KEY.  The path is resolved relative to this file so the app
# works whether uvicorn is started from backend/ or the project root.
_backend_dir = _Path(__file__).resolve().parent.parent
load_dotenv(_backend_dir / ".env")

from blockchain.alchemy_client import (
    AlchemyAPIError,
    AlchemyConfigError,
    AlchemyHTTPError,
)
from blockchain.models import WalletTransfers
from blockchain.service import BlockchainService
from blockchain.validators import InvalidAddressError

app = FastAPI(
    title="CryptoTrace API",
    version="0.1.0",
    description="SIH26182 blockchain investigation and VASP attribution API",
)

service = BlockchainService()


class WalletRequest(BaseModel):
    address: str = Field(..., min_length=10)


@app.get("/")
def root():
    return {
        "project": "SIH26182-CryptoTrace",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


@app.get(
    "/api/v1/wallets/{address}/transfers",
    response_model=WalletTransfers,
    responses={
        200: {"description": "Transfers retrieved"},
        400: {"description": "Invalid wallet address"},
        502: {"description": "Blockchain provider / API failure"},
        500: {"description": "Unexpected internal error"},
    },
)
async def get_wallet_transfers(
    address: str = Path(..., description="Ethereum wallet address (0x...)"),
    limit: int | None = Query(
        None, ge=1, le=10000, description="Optional cap on number of transfers returned"
    ),
):
    """Return normalized incoming/outgoing transfers for a wallet."""
    try:
        result = await service.get_wallet_transfers(address, limit=limit)
    except InvalidAddressError:
        raise HTTPException(status_code=400, detail="Invalid Ethereum address.")
    except (AlchemyConfigError, AlchemyHTTPError, AlchemyAPIError):
        raise HTTPException(
            status_code=502, detail="Blockchain provider is unavailable or misconfigured."
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected internal error.")
    return result


@app.post("/api/v1/investigations")
def create_investigation(request: WalletRequest):
    # Kept for backward compatibility. Wallet transfer ingestion is provided by
    # GET /api/v1/wallets/{address}/transfers.
    return {
        "wallet": request.address,
        "status": "created",
        "transactions": [],
        "message": "Use GET /api/v1/wallets/{address}/transfers for blockchain ingestion.",
    }
