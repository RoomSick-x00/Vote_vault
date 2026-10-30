"""Environment configuration for the VoteVault backend.

All variable names match the root `.env.example` inventory. Times are naive UTC
throughout the backend (see `app.db.base.utcnow`).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- application ---
    app_env: str = "development"

    # --- database (Supabase PostgreSQL in real deployments) ---
    # Supabase pooler example:
    # postgresql+psycopg://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
    database_url: str = "sqlite:///./votevault-dev.db"

    # --- Supabase Auth (JWT verification; either JWKS (RS256) or shared secret (HS256)) ---
    supabase_url: str = ""
    supabase_jwks_url: str = ""
    supabase_jwt_secret: str = ""
    # Public anon key — enables the signup/login proxy endpoints (/auth/signup, /auth/login).
    supabase_anon_key: str = ""

    # --- HTTP ---
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- blockchain (Hardhat local chain, per docs/decisions/2026-10-31-blockchain-interface.md) ---
    blockchain_rpc_url: str = ""  # e.g. http://127.0.0.1:8545
    blockchain_chain_id: int = 31337  # Hardhat network chain id
    ballot_registry_contract_address: str = ""
    local_chain_signer_private_key: str = ""  # relayer key; backend-only, never commit
    # Deployment artifact written by blockchain/scripts/deploy.js (address + ABI +
    # runtimeCodeHash + relayer). When set and present, the publisher loads the
    # contract from here and validates the deployed bytecode before first use.
    blockchain_deployment_file: str = "blockchain/deployments/localhost.json"

    # --- publication jobs ---
    publication_max_attempts: int = 5
    publication_retry_delay_seconds: float = 5.0  # base delay; grows exponentially per attempt
    publication_confirmations: int = 1  # blocks required beyond the receipt (Hardhat automines)
    publication_receipt_timeout_seconds: float = 30.0
    publication_poll_interval_seconds: float = 2.0
    run_background_publisher: bool = True

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def jwks_url(self) -> str:
        """JWKS endpoint: explicit setting wins, otherwise derived from SUPABASE_URL."""
        if self.supabase_jwks_url:
            return self.supabase_jwks_url
        if self.supabase_url:
            return self.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
        return ""

    @property
    def jwt_issuer(self) -> str:
        """Expected `iss` claim; empty string disables the check (local/dev mode)."""
        if self.supabase_url:
            return self.supabase_url.rstrip("/") + "/auth/v1"
        return ""
