"""Declarative base, naming conventions, and shared column mixins."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, MetaData, Uuid as SaUuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Stable constraint names matter: they keep Alembic migrations deterministic and
# make integrity errors identifiable across PostgreSQL and SQLite.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s_%(column_1_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    """Naive UTC timestamp.

    The backend stores all timestamps as naive UTC (`TIMESTAMP WITHOUT TIME ZONE`)
    so PostgreSQL and SQLite behave identically in tests; serializers emit `...Z`.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class IdMixin:
    id: Mapped[uuid.UUID] = mapped_column(SaUuid(), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )
