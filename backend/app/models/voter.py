"""Voter roster: uploaded by the organizer, NOT Supabase accounts.

The roster is private organizer-held data. A roster row is the voter identity
for one election: the voter identifies with the election's `identityColumns`
(name and/or roll number), proves control of the OTP channel contact, and gets
a short-lived voter session token. `has_voted` is deliberately NOT stored —
it derives from the ballots table (single source of truth).
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid as SaUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Voter(Base, IdMixin, TimestampMixin):
    __tablename__ = "voters"

    election_id: Mapped[uuid.UUID] = mapped_column(
        SaUuid(), ForeignKey("elections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    roll_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (
        # Roll numbers identify within one election; NULLs (name-identity
        # elections) don't collide in SQL unique constraints.
        UniqueConstraint("election_id", "roll_no", name="uq_voters_election_roll_no"),
    )
