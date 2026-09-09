from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from graph.api import close_driver, router as graph_router
from graph.db_loader import GraphLoadError


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_driver()


app = FastAPI(
    title="CryptoTrace API",
    version="0.1.0",
    description="SIH26182 blockchain investigation and VASP attribution API",
    lifespan=lifespan,
)

app.include_router(graph_router)


@app.exception_handler(GraphLoadError)
async def graph_load_error_handler(request: Request, exc: GraphLoadError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


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
