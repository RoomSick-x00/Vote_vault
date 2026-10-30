"""Auth routes: whoami, organizer signup, login.

Signup/login relay credentials to Supabase Auth (public anon key only) and
then persist local state — profile row, and for signup the organization plus
owner membership — in one database transaction. The returned access_token is
the Supabase JWT, which every protected endpoint already verifies.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.auth.supabase_auth import SupabaseAuthError, auth_error_to_api
from app.auth.tokens import AuthUser
from app.db.base import utcnow
from app.errors import ApiError
from app.models import OrgMembership, Organization, Profile
from app.schemas.auth import (
    AuthMeOut,
    AuthSessionOut,
    AuthUserOut,
    LoginIn,
    OrgRefOut,
    SignupIn,
)

router = APIRouter()


@router.get("/auth/me", response_model=AuthMeOut)
def whoami(user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)) -> AuthMeOut:
    profile = db.get(Profile, user.id)
    return AuthMeOut(
        user_id=str(user.id),
        email=profile.email if profile else user.email,
        full_name=profile.full_name if profile else None,
        organizations=_organizations(db, user.id),
    )


@router.post("/auth/signup", status_code=201, response_model=AuthSessionOut)
def signup(payload: SignupIn, request: Request, db: Session = Depends(get_db)) -> AuthSessionOut:
    auth_client = _auth_client(request)
    try:
        session = auth_client.sign_up(
            payload.email, payload.password, payload.full_name
        )
    except SupabaseAuthError as exc:
        raise auth_error_to_api(exc) from exc

    upstream_user = session["user"]
    user_id = _user_id(upstream_user)

    # Local state in one transaction: profile + organization + owner membership.
    profile = db.get(Profile, user_id)
    if profile is None:
        profile = Profile(user_id=user_id, email=payload.email, full_name=payload.full_name)
        db.add(profile)
    else:
        profile.email = payload.email
        profile.full_name = payload.full_name

    organization = Organization(name=payload.organization_name, created_by=user_id)
    db.add(organization)
    db.flush()
    db.add(OrgMembership(organization_id=organization.id, user_id=user_id, role="owner"))
    db.commit()

    return AuthSessionOut(
        access_token=session["access_token"],
        refresh_token=session.get("refresh_token"),
        expires_in=int(session.get("expires_in") or 3600),
        user=AuthUserOut(
            user_id=str(user_id), email=payload.email, full_name=payload.full_name
        ),
        organizations=[OrgRefOut(
            organization_id=str(organization.id),
            name=organization.name,
            role="owner",
        )],
    )


@router.post("/auth/login", response_model=AuthSessionOut)
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)) -> AuthSessionOut:
    auth_client = _auth_client(request)
    try:
        session = auth_client.sign_in_with_password(payload.email, payload.password)
    except SupabaseAuthError as exc:
        raise auth_error_to_api(exc) from exc

    upstream_user = session["user"]
    user_id = _user_id(upstream_user)
    full_name = _full_name(upstream_user)
    synced = _sync_profile_on_login(db, user_id, payload.email, full_name or None)
    full_name = full_name or synced

    return AuthSessionOut(
        access_token=session["access_token"],
        refresh_token=session.get("refresh_token"),
        expires_in=int(session.get("expires_in") or 3600),
        user=AuthUserOut(
            user_id=str(user_id),
            email=str(upstream_user.get("email") or payload.email),
            full_name=full_name or "",
        ),
        organizations=_organizations(db, user_id),
    )


def _auth_client(request: Request):
    client = request.app.state.supabase_auth
    if client is None:
        raise ApiError(
            503,
            "AUTH_UPSTREAM_NOT_CONFIGURED",
            "Signup/login need SUPABASE_URL and SUPABASE_ANON_KEY in the backend environment.",
        )
    return client


def _user_id(upstream_user: dict):
    from app.errors import ApiError as _ApiError
    import uuid as _uuid

    try:
        return _uuid.UUID(str(upstream_user["id"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise _ApiError(502, "AUTH_UPSTREAM_ERROR", "Auth provider returned an unusable user id.") from exc


def _full_name(upstream_user: dict) -> str:
    metadata = upstream_user.get("user_metadata") or {}
    return str(metadata.get("full_name") or "").strip()


def _sync_profile_on_login(
    db: Session, user_id, email: str, full_name: str | None = None
) -> str | None:
    """Login also syncs the local profile; returns the stored full name if known."""
    profile = db.get(Profile, user_id)
    if profile is None:
        profile = Profile(user_id=user_id, email=email, full_name=full_name or email)
        db.add(profile)
        db.commit()
        return full_name
    if profile.email != email:
        profile.email = email
    # Backfill the name when the row only carries the email placeholder.
    if full_name and profile.full_name in (None, "", email):
        profile.full_name = full_name
    db.commit()
    return profile.full_name if profile.full_name != email else None


def _organizations(db: Session, user_id) -> list[OrgRefOut]:
    rows = db.execute(
        select(Organization, OrgMembership)
        .join(OrgMembership, OrgMembership.organization_id == Organization.id)
        .where(OrgMembership.user_id == user_id)
        .order_by(Organization.created_at)
    ).all()
    return [
        OrgRefOut(organization_id=str(org.id), name=org.name, role=membership.role)
        for org, membership in rows
    ]
