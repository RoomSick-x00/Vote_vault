"""Elections: lifecycle draft -> open -> closing -> closed, voting window settings,
shareable voter code, and the organizer-configured voter schema.

`voter_schema` decides how uploaded-roster voters identify themselves:
{"identityColumns": ["name"|"rollNo", ...], "otpChannels": ["email"|"phone", ...]}.
The OTP channel's column (email/phone) becomes mandatory in the roster.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, JSON, String, Uuid as SaUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin

ELECTION_STATUSES = ("draft", "open", "closing", "closed")
IDENTITY_COLUMNS = ("name", "rollNo")
OTP_CHANNELS = ("email", "phone")

DEFAULT_VOTER_SCHEMA = {"identityColumns": ["rollNo"], "otpChannels": ["email"]}


class Election(Base, IdMixin, TimestampMixin):
    __tablename__ = "elections"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        SaUuid(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    # Short shareable code voters type in (also the QR payload). Unique, unguessable
    # enough for a campus demo; not a secret.
    code: Mapped[str] = mapped_column(String(12), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    voter_schema: Mapped[dict] = mapped_column(JSON(), nullable=False, default=lambda: dict(DEFAULT_VOTER_SCHEMA))
    opens_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'open', 'closing', 'closed')",
            name="status_values",
        ),
    )
