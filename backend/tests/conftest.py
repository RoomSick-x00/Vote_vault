"""Pytest fixtures.

The test database is a REAL PostgreSQL (bundled via pgserver, no root needed)
so migration DDL, transactions, and the one-ballot-per-voter unique constraint
race behave exactly as on Supabase. Set VOTEVAULT_TEST_DATABASE_URL to point at
any Postgres, or VOTEVAULT_TEST_DB=sqlite to force the SQLite fallback.
Migrations are applied through Alembic — never create_all — matching how the
real database is managed.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fake_chain import FakeChainPublisher  # noqa: E402
from helpers import TEST_JWT_SECRET  # noqa: E402


def _sqlite_url() -> str:
    tmp = Path(tempfile.mkdtemp(prefix="votevault-sqlite-"))
    return f"sqlite:///{tmp / 'test.db'}"


def _resolve_database_url() -> str:
    override = os.environ.get("VOTEVAULT_TEST_DATABASE_URL")
    if override:
        return override
    if os.environ.get("VOTEVAULT_TEST_DB", "").lower() == "sqlite":
        return _sqlite_url()
    try:
        import pgserver

        server = pgserver.get_server(os.environ.get("VOTEVAULT_PG_DIR", "/tmp/votevault-test-pg"))
        return server.get_uri().replace("postgresql://", "postgresql+psycopg://", 1)
    except Exception as exc:  # pragma: no cover - environment without pgserver
        print(f"[conftest] pgserver unavailable ({exc}); falling back to SQLite")
        return _sqlite_url()


@pytest.fixture(scope="session")
def database_url() -> str:
    url = _resolve_database_url()
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    return url


@pytest.fixture(scope="session")
def sessionmaker_(database_url):
    from app.db.session import create_engine_and_sessionmaker

    engine, factory = create_engine_and_sessionmaker(database_url)
    yield factory
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables(sessionmaker_):
    yield
    from sqlalchemy import text

    table_order = [
        "voter_otp_challenges",
        "profiles",
        "publication_jobs",
        "ballots",
        "voters",
        "candidates",
        "elections",
        "org_memberships",
        "organizations",
    ]
    with sessionmaker_() as db:
        for table in table_order:
            db.execute(text(f"DELETE FROM {table}"))
        db.commit()


@pytest.fixture()
def fake_publisher() -> FakeChainPublisher:
    return FakeChainPublisher()


@pytest.fixture()
def app(database_url, sessionmaker_, fake_publisher):
    from app.config import Settings
    from app.main import create_app

    settings = Settings(
        database_url=database_url,
        supabase_jwt_secret=TEST_JWT_SECRET,
        run_background_publisher=False,
        publication_retry_delay_seconds=0,
        publication_receipt_timeout_seconds=1,
        publication_max_attempts=3,
    )
    return create_app(
        settings=settings,
        publisher=fake_publisher,
        run_background_publisher=False,
    )


@pytest.fixture()
def fake_supabase(app):
    """Wire the fake auth proxy into the app (no real Supabase in tests)."""
    from fake_supabase import FakeSupabaseAuth

    client = FakeSupabaseAuth(TEST_JWT_SECRET)
    app.state.supabase_auth = client
    return client


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app)
