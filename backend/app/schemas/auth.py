from __future__ import annotations

import uuid

from pydantic import EmailStr, Field

from app.schemas.common import APIModel


class SignupIn(APIModel):
    """Organizer signup. Credentials are relayed to Supabase Auth; the full
    name is stored in the profile and the organization is created with the
    signer as owner — all in one request."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    organization_name: str = Field(min_length=1, max_length=200)


class LoginIn(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthUserOut(APIModel):
    user_id: str
    email: str
    full_name: str


class OrgRefOut(APIModel):
    organization_id: str
    name: str
    role: str


class AuthSessionOut(APIModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int
    user: AuthUserOut
    organizations: list[OrgRefOut]


class AuthMeOut(APIModel):
    user_id: str
    email: str | None = None
    full_name: str | None = None
    organizations: list[OrgRefOut] = []
