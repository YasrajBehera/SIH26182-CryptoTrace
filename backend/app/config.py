import os
from pathlib import Path
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.security import new_token_secret

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
_BACKEND_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

# Development-only token secret location. Git-ignored; never shipped.
_DEV_SECRET_FILE = Path(__file__).resolve().parent.parent / ".auth_dev_secret"


class Settings(BaseSettings):
    app_name: str = "CryptoTrace"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    alchemy_api_key: str = ""

    database_url: str = (
        "postgresql+psycopg://cryptotrace:cryptotrace@localhost:5432/cryptotrace"
    )

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "change_me"

    # ---- Security ---------------------------------------------------------
    # Token-signing secret. In development an empty value generates a fresh
    # random secret at boot and reports it ONCE (never persisted). Production
    # deployments must set AUTH_SECRET explicitly via env.
    auth_secret: str = ""
    auth_token_ttl_minutes: int = 120

    # CORS. Dev default covers the Vite dev server origins.
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]

    # ---- Rate limiting (in-memory, single instance) ----------------------
    rate_limit_max_requests: int = 120
    rate_limit_window_seconds: int = 60
    login_rate_limit: int = 5
    login_rate_window_seconds: int = 60
    analyze_rate_limit: int = 10

    # ---- Demo seeding ------------------------------------------------------
    # When true, ensure_demo_seed() provisions role-scaffolding demo users if
    # none exist. Passwords come from DEMO_SEED_PASSWORD env, or a one-time
    # random password printed to stdout (never stored as plaintext).
    demo_seed_enabled: bool = True
    demo_seed_password: str = ""

    model_config = SettingsConfigDict(
        env_file=(_ENV_FILE, _BACKEND_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def resolved_auth_secret(self, dev_file: Optional[Path] = None) -> str:
        """Return the effective token secret.

        Production must set AUTH_SECRET explicitly. In development a random
        secret is generated once and persisted to a git-ignored dotfile so
        tokens keep verifying across backend restarts. The secret value is
        never printed or logged; only the one-time warning mentions it exists.
        ``dev_file`` is injectable for tests.
        """
        if self.auth_secret:
            return self.auth_secret
        file = dev_file or _DEV_SECRET_FILE
        try:
            if file.exists():
                stored = file.read_text(encoding="utf-8").strip()
                if stored:
                    return stored
        except OSError:
            pass
        fresh = new_token_secret()
        try:
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(fresh + "\n", encoding="utf-8")
            if os.name != "nt":
                os.chmod(file, 0o600)
            print(
                "[cryptotrace] WARNING: AUTH_SECRET is not set. A development "
                "secret was generated and stored in an ignored dotfile "
                "(.auth_dev_secret). Set AUTH_SECRET in production.",
                flush=True,
            )
        except OSError:
            pass
        return fresh


settings = Settings()