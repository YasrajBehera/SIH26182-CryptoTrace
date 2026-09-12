from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.audit.api import router as audit_router
from app.auth.api import admin_router as admin_users_router
from app.auth.api import router as auth_router
from app.auth.deps import require_permission
from app.config import settings as _settings
from graph.api import close_driver, router as graph_router
from graph.db_loader import GraphLoadError

# ---- Routers ----------------------------------------------------------------
# Router-level RBAC dependencies enforce permissions server-side. The backend
# is the sole authorization authority; the UI permission grid is cosmetic.
from attribution.api import router as attribution_router
from cases.api import router as cases_router
from evidence.api import router as evidence_router
from intelligence.api import router as intelligence_router
from pipeline.api import router as pipeline_router
from reports.api import router as reports_router
from risk.api import router as risk_router
from sahyog.api import router as sahyog_router
from wallets.api import router as wallets_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.config import settings
    from app.auth.service import get_user_service
    from app.db import database_available, ensure_database_tables

    # Boot integration with the live PostgreSQL container: when Postgres is
    # reachable, provision the schema so users/cases/transactions/attribution/
    # evidence/risk/audit/sahyog tables exist before the API serves. When it is
    # unreachable the repositories fall back to in-memory stores as designed.
    if database_available():
        try:
            ensure_database_tables()
        except Exception:
            # A schema failure must never prevent the API from serving.
            pass

    # Opt-in boot seeding: only when an explicit DEMO_SEED_PASSWORD is set.
    # Generates PBKDF2-hashed users; the plaintext password is never stored.
    if settings.demo_seed_enabled and settings.demo_seed_password:
        try:
            get_user_service().ensure_demo_seed()
        except Exception:
            # Seeding must never prevent the API from serving.
            pass
    yield
    close_driver()

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

from app.middleware import (
    RateLimitMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
    cors_configuration,
)

app = FastAPI(
    title="CryptoTrace API",
    version="0.1.0",
    description="SIH26182 blockchain investigation and VASP attribution API",
    lifespan=lifespan,
)

# ---- HTTP security envelope -------------------------------------------------
# Order matters: the LAST middleware added runs FIRST for incoming requests, so
# CORS is outermost, then request ids/headers, then rate limiting.

app.add_middleware(
    CORSMiddleware,
    **cors_configuration(origins=_settings.cors_origins),
)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    limits={
        "/api/v1/auth/login": (
            _settings.login_rate_limit,
            _settings.login_rate_window_seconds,
        ),
        "/api/v1/investigations": (
            _settings.analyze_rate_limit,
            _settings.rate_limit_window_seconds,
        ),
    },
    default=(_settings.rate_limit_max_requests, _settings.rate_limit_window_seconds),
)

app.include_router(
    graph_router,
    dependencies=[Depends(require_permission("graph.read"))],
)
app.include_router(
    intelligence_router,
    dependencies=[Depends(require_permission("attribution.read"))],
)
app.include_router(
    attribution_router,
    dependencies=[Depends(require_permission("attribution.read"))],
)
app.include_router(
    evidence_router,
    dependencies=[Depends(require_permission("evidence.read"))],
)
app.include_router(
    pipeline_router,
    dependencies=[Depends(require_permission("wallet.analyze"))],
)
app.include_router(cases_router)
app.include_router(wallets_router)
app.include_router(risk_router)
app.include_router(reports_router)
app.include_router(sahyog_router)
app.include_router(auth_router)
app.include_router(admin_users_router)
app.include_router(audit_router)


@app.exception_handler(GraphLoadError)
async def graph_load_error_handler(request: Request, exc: GraphLoadError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


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
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        502: {"description": "Blockchain provider / API failure"},
        500: {"description": "Unexpected internal error"},
    },
)
async def get_wallet_transfers(
    address: str = Path(..., description="Ethereum wallet address (0x...)"),
    limit: int | None = Query(
        None, ge=1, le=10000, description="Optional cap on number of transfers returned"
    ),
    _current_user=Depends(require_permission("wallet.read")),
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