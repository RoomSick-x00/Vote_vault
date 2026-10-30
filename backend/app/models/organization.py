"""Organizations and organizer membership/roles.

`user_id` refers to a Supabase Auth user (auth.users.id). It is intentionally
not a foreign key: the auth schema belongs to Supabase and must keep working
against plain PostgreSQL in tests.
"""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint, Uuid as SaUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin

ORGANIZER_ROLES = ("owner", "organizer")


class Organization(Base, IdMixin, TimestampMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(SaUuid(), nullable=False)


class OrgMembership(Base, IdMixin, TimestampMixin):
    __tablename__ = "org_memberships"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        SaUuid(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(SaUuid(), nullable=False, index=True)
    role: Mapped[str] = mapped_column(nullable=False)

    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'organizer')",
            name="role_values",
        ),
        UniqueConstraint("organization_id", "user_id", name="uq_org_memberships_org_user"),
    )
