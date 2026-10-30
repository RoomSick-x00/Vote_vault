"""VoteVault backend application factory.

Run locally:  uvicorn app.main:app --reload --port 8000  (from backend/)
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.auth.tokens import TokenVerifier
from app.blockchain.publisher import UnavailablePublisher, Web3RegistryPublisher
from app.config import Settings
from app.db.session import create_engine_and_sessionmaker
from app.errors import install_error_handlers
from app.services import publication_service, tally_service

log = logging.getLogger("votevault")

DESCRIPTION = (
    "VoteVault milestone-1 backend (synthetic test data). Ballot commitments are "
    "published to a local Hardhat chain; results are a backend demo tally — "
    "independent private tally verification is pending."
)


async def _publication_loop(app: FastAPI) -> None:
    settings: Settings = app.state.settings
    while True:
        try:
            await asyncio.to_thread(
                publication_service.process_due_jobs,
                app.state.sessionmaker,
                app.state.publisher,
                settings,
            )
        except asyncio.CancelledError:  # pragma: no cover - shutdown
            raise
        except Exception:  # noqa: BLE001 - the loop must survive anything
            log.exception("publication loop iteration failed")
        await asyncio.sleep(settings.publication_poll_interval_seconds)


def create_app(
    settings: Settings | None = None,
    publisher=None,
    run_background_publisher: bool | None = None,
) -> FastAPI:
    settings = settings or Settings()
    engine, session_factory = create_engine_and_sessionmaker(settings.database_url)

    if publisher is None:
        if settings.blockchain_configured:
            publisher = Web3RegistryPublisher(
                rpc_url=settings.blockchain_rpc_url,
                contract_address=settings.ballot_registry_contract_address,
                signer_private_key=settings.local_chain_signer_private_key,
                chain_id=settings.blockchain_chain_id,
            )
        else:
            publisher = UnavailablePublisher()
    run_bg = settings.run_background_publisher if run_background_publisher is None else run_background_publisher

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task: asyncio.Task | None = None
        if run_bg:
            log.info(
                "background publisher started (interval=%ss, publisher=%s)",
                settings.publication_poll_interval_seconds,
                getattr(publisher, "name", type(publisher).__name__),
            )
            task = asyncio.create_task(_publication_loop(app))
        yield
        if task is not None:
            task.cancel()

    app = FastAPI(
        title="VoteVault Backend",
        version="0.1.0",
        description=DESCRIPTION,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = session_factory
    app.state.publisher = publisher
    app.state.run_background_publisher = run_bg
    app.state.token_verifier = TokenVerifier(
        jwks_url=settings.jwks_url,
        jwt_secret=settings.supabase_jwt_secret,
        issuer=settings.jwt_issuer,
    )
    if settings.supabase_url and settings.supabase_anon_key:
        from app.auth.supabase_auth import SupabaseAuthClient

        app.state.supabase_auth = SupabaseAuthClient(settings.supabase_url, settings.supabase_anon_key)
    else:
        app.state.supabase_auth = None

    origins = settings.cors_origins
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials="*" not in origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    install_error_handlers(app)
    app.include_router(api_router)

    @app.get("/", tags=["meta"])
    def root() -> dict:
        return {
            "service": "votevault-backend",
            "status": "ok",
            "publisher": getattr(publisher, "name", type(publisher).__name__),
            "results_disclaimer": tally_service.TALLY_DISCLAIMER,
        }

    return app


app = create_app()
