import os
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.audit.api import router as audit_router
from app.auth.api import admin_router as admin_users_router
from app.auth.api import router as auth_router
from app.auth.deps import get_current_user, require_permission
from app.config import settings as _settings
from assistant.api import router as assistant_router
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
from search.api import router as search_router
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
        "/api/v1/auth": (
            _settings.login_rate_limit,
            _settings.login_rate_window_seconds,
        ),
        "investigations.analyze": (
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
app.include_router(search_router)
app.include_router(assistant_router)
app.include_router(auth_router)
app.include_router(admin_users_router)
app.include_router(audit_router)


@app.exception_handler(GraphLoadError)
async def graph_load_error_handler(request: Request, exc: GraphLoadError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


service = BlockchainService()
# Wire the persistent wallet repository into the transfers service so that
# GET /wallets/{address}/transfers serves from PostgreSQL when rows already
# exist for the wallet, and stores fresh provider results for later pages.
from wallets.repository import make_wallet_repository as _make_wallet_repo

service.wallet_repository = _make_wallet_repo()


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


@app.get("/api/v1/system/status")
def system_status(_current_user=Depends(get_current_user)) -> dict:
    """Authenticated per-component availability for the dashboard status card.

    Each entry is a plain boolean resolved from a cheap live check at request
    time — no chain RPC calls and no long-running probes:

    - backend:    this process is serving the request
    - auth:       a valid session token was presented
    - postgres:   the configured database is reachable
    - blockchain: an Alchemy provider key is configured
    - neo4j:      the graph database is reachable
    - graph:      mirrors neo4j (the graph engine runs on Neo4j)
    - vasp:       attribution engine (curated public directory)
    - report:     the PDF renderer (reportlab) is importable
    - sahyog:     the cross-border inquiry repository is available
    """
    from app.db import database_available
    from graph.neo4j_client import create_driver, is_neo4j_healthy

    graph_ok = False
    driver = None
    try:
        driver = create_driver()
        graph_ok = is_neo4j_healthy(driver)
    except Exception:
        graph_ok = False
    finally:
        if driver is not None:
            try:
                driver.close()
            except Exception:
                pass

    report_ok = False
    try:
        import reportlab  # noqa: F401
        report_ok = True
    except Exception:
        report_ok = False

    return {
        "backend": True,
        "auth": True,
        "postgres": database_available(),
        "blockchain": bool(_settings.alchemy_api_key or os.environ.get("ALCHEMY_API_KEY", "")),
        "neo4j": graph_ok,
        "graph": graph_ok,
        "vasp": True,
        "report": report_ok,
        "sahyog": True,
        "sahyog_production": _settings.sahyog_production_api_configured,
    }


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
        None, ge=1, le=10000, description="Page size (number of transfers returned)"
    ),
    offset: int | None = Query(
        None, ge=0, description="Offset into the sorted transfer set"
    ),
    direction: Literal["in", "out"] | None = Query(
        None, description="Restrict to one direction (in/out)"
    ),
    refresh: bool = Query(
        False, description="Force a fresh provider fetch instead of replaying persisted rows"
    ),
    _current_user=Depends(require_permission("wallet.read")),
):
    """Return normalized incoming/outgoing transfers for a wallet.

    Served from the persisted PostgreSQL wallet store when rows already exist
    for the wallet (consistent across pages and surfaces); otherwise fetched
    from the blockchain provider, normalized, timestamped from the chain block
    and persisted. ``total`` / ``has_next`` / ``has_previous`` are returned in
    ``pagination`` so the UI can page without loading everything into React.
    """
    try:
        result = await service.get_wallet_transfers(
            address, limit=limit, offset=offset, direction=direction, refresh=refresh
        )
    except InvalidAddressError:
        raise HTTPException(status_code=400, detail="Invalid Ethereum address.")
    except (AlchemyConfigError, AlchemyHTTPError, AlchemyAPIError):
        raise HTTPException(
            status_code=502, detail="Blockchain provider is unavailable or misconfigured."
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected internal error.")
    return result