"""Publication jobs: what must reach the BallotRegistry contract, and how far it got.

A job row is created in the SAME database transaction as the state change it
anchors (ballot accepted, election opened, result computed). Chain submission is
a separate best-effort operation driven by this table: attempts/backoff/tx hash/
block number record the truth. Exposed statuses are exactly pending / confirmed
/ failed — the database and the blockchain never share a transaction and the API
never pretends otherwise.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Uuid as SaUuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin

JOB_TYPES = (
    "register_election",
    "open_election",
    "publish_ballot",
    "close_election",
    "publish_result",
)
JOB_STATUSES = ("pending", "confirmed", "failed")


class PublicationJob(Base, IdMixin, TimestampMixin):
    __tablename__ = "publication_jobs"

    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    election_id: Mapped[uuid.UUID] = mapped_column(
        SaUuid(), ForeignKey("elections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ballot_id: Mapped[uuid.UUID | None] = mapped_column(
        SaUuid(), ForeignKey("ballots.id", ondelete="CASCADE"), nullable=True
    )
    # Encoded call arguments as 0x-hex strings, e.g. for publish_ballot:
    # {"election_id": "0x…", "ballot_id": "0x…", "commitment": "0x…"}
    payload: Mapped[dict] = mapped_column(JSON(), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer(), nullable=False, default=5)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True, index=True)
    tx_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    block_number: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text(), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "job_type IN ('register_election', 'open_election', 'publish_ballot', "
            "'close_election', 'publish_result')",
            name="job_type_values",
        ),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'failed')",
            name="status_values",
        ),
        CheckConstraint("attempts >= 0", name="attempts_non_negative"),
    )
