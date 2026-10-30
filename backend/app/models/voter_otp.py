"""OTP challenges for the voter identify -> verify flow.

Codes are stored hashed; the identify token's jti binds the challenge to one
identify step. Attempts are capped and consumed challenges cannot be reused.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid as SaUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class VoterOtpChallenge(Base, IdMixin, TimestampMixin):
    __tablename__ = "voter_otp_challenges"

    election_id: Mapped[uuid.UUID] = mapped_column(
        SaUuid(), ForeignKey("elections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    voter_id: Mapped[uuid.UUID] = mapped_column(
        SaUuid(), ForeignKey("voters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identify_jti: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[str] = mapped_column(String(8), nullable=False)  # email | phone
    contact: Mapped[str] = mapped_column(String(254), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(66), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
