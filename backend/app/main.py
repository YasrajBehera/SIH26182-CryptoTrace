from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(
    title="CryptoTrace API",
    version="0.1.0",
    description="SIH26182 blockchain investigation and VASP attribution API",
)


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


@app.post("/api/v1/investigations")
def create_investigation(request: WalletRequest):
    # Initial contract only. Real blockchain ingestion will be added by Member 1.
    return {
        "wallet": request.address,
        "status": "created",
        "transactions": [],
        "message": "Blockchain ingestion module is not connected yet.",
    }
