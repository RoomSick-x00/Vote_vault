"""Eligible test voters for an election.

`user_id` is a Supabase Auth user id (synthetic test users in milestone 1).
The unique constraint makes double-provisioning impossible and mirrors the
ballot constraint that guarantees one ballot per voter.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid as SaUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class EligibleVoter(Base, IdMixin, TimestampMixin):
    __tablename__ = "eligible_voters"

    election_id: Mapped[uuid.UUID] = mapped_column(
        SaUuid(), ForeignKey("elections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(SaUuid(), nullable=False)

    __table_args__ = (
        UniqueConstraint("election_id", "user_id", name="uq_eligible_voters_election_user"),
    )
