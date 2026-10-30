"""Ballots (milestone-1 model; will change for anonymous/encrypted voting).

One accepted ballot per (election, voter) is enforced by the database, not just
by application checks — the unique constraint is what makes simultaneous
submissions safe. `voter_id` references the uploaded roster (`voters.id`), not
a Supabase account. `nonce` and `commitment` implement the documented commitment
scheme; the ballot choice is stored in the clear in this skeleton and must be
treated as private organizer-held data. Ballot rows are never exposed to
organizers through the API — only aggregate counts and publication statuses are.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, Uuid as SaUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Ballot(Base, IdMixin, TimestampMixin):
    __tablename__ = "ballots"

    election_id: Mapped[uuid.UUID] = mapped_column(
        SaUuid(), ForeignKey("elections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    voter_id: Mapped[uuid.UUID] = mapped_column(
        SaUuid(), ForeignKey("voters.id"), nullable=False
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        SaUuid(), ForeignKey("candidates.id"), nullable=False
    )
    nonce: Mapped[str] = mapped_column(String(64), nullable=False)  # 32 bytes, hex
    commitment: Mapped[str] = mapped_column(String(66), nullable=False)  # 0x + 64 hex
    accepted: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)

    __table_args__ = (
        # THE one-ballot-per-voter guarantee; races surface as IntegrityError.
        UniqueConstraint("election_id", "voter_id", name="uq_ballots_election_voter"),
    )
