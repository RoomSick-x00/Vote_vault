"""Engine and session factory creation.

`create_engine_and_sessionmaker` is used both by the app factory and by tests,
so tests exercise the same engine configuration as production (minus the URL).
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def create_engine_and_sessionmaker(database_url: str) -> tuple[Engine, sessionmaker[Session]]:
    connect_args: dict = {}
    if database_url.startswith("sqlite"):
        # TestClient serves requests from worker threads; SQLite needs both opts.
        connect_args = {"check_same_thread": False, "timeout": 30}
    engine = create_engine(
        database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    session_factory = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False, future=True
    )
    return engine, session_factory
