from __future__ import annotations

from pydantic import BaseModel


class AuthMeOut(BaseModel):
    user_id: str
    email: str | None = None
