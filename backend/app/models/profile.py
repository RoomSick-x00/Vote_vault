"""Organizer profiles (milestone-1).

`user_id` is the Supabase Auth user id — same no-FK policy as memberships:
auth.users belongs to Supabase. Email/full_name are synced from Supabase on
signup and login; credentials themselves never touch this database.
"""

from __future__ import annotations

import uuid

from sqlalchemy import String, Uuid as SaUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Profile(Base, TimestampMixin):
    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(SaUuid(), primary_key=True)
    email: Mapped[str] = mapped_column(nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
