"""Candidates linked to an election.

`chain_index` is the 0-based immutable position used in the ballot commitment
preimage and the result hash (see docs/decisions/2026-10-30-blockchain-interface.md).
It is assigned at creation from the election's current candidate count, so it is
stable as long as candidates are only added while the election is a draft.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, Uuid as SaUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Candidate(Base, IdMixin, TimestampMixin):
    __tablename__ = "candidates"

    election_id: Mapped[uuid.UUID] = mapped_column(
        SaUuid(), ForeignKey("elections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    chain_index: Mapped[int] = mapped_column(Integer(), nullable=False)

    __table_args__ = (
        UniqueConstraint("election_id", "name", name="uq_candidates_election_name"),
        UniqueConstraint("election_id", "chain_index", name="uq_candidates_election_chain_index"),
    )
