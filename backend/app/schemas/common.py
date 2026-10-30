"""Shared schema plumbing. All timestamps serialize as UTC ISO 8601 with `Z`."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer, field_validator


def _serialize_utc(dt: datetime) -> str:
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat(timespec="seconds") + "Z"


UtcIso = Annotated[datetime, PlainSerializer(_serialize_utc, return_type=str, when_used="unless-none")]


class APIModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


def normalize_to_naive_utc(value: datetime) -> datetime:
    """Stored timestamps are naive UTC; accept aware ISO input by converting."""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


utc_input_validator = field_validator("opens_at", "closes_at", mode="after")(normalize_to_naive_utc)
