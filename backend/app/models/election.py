"""Elections: lifecycle draft -> open -> closed plus optional open/close window settings.

`opens_at`/`closes_at` are organizer-specified settings; when set they bound
ballot acceptance while the status is `open` (polling-place style scheduling).
The status column remains authoritative for the lifecycle itself.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid as SaUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin

ELECTION_STATUSES = ("draft", "open", "closed")


class Election(Base, IdMixin, TimestampMixin):
    __tablename__ = "elections"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        SaUuid(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    opens_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'open', 'closed')",
            name="status_values",
        ),
    )
