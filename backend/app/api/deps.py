"""FastAPI dependencies: DB session, current user, election access, organizer role."""

from __future__ import annotations

import uuid

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.tokens import AuthUser
from app.config import Settings
from app.errors import ApiError
from app.models import Election, OrgMembership, Voter

_bearer = HTTPBearer(auto_error=False)

ORGANIZER_LEVEL_ROLES = ("owner", "organizer")


def get_db(request: Request) -> Session:
    db = request.app.state.sessionmaker()
    try:
        yield db
    finally:
        db.close()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_current_user(
    request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)
) -> AuthUser:
    if credentials is None:
        raise ApiError(401, "UNAUTHENTICATED", "Missing bearer token.")
    return request.app.state.token_verifier.verify(credentials.credentials)


def get_voter_session(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> tuple[Voter, Election]:
    """Voter-flow auth: backend-issued session token (scope "voter") minted after
    OTP verification. Supabase tokens are rejected here (no voter scope), and
    voter tokens are rejected at organizer endpoints (no `sub`)."""
    if credentials is None:
        raise ApiError(401, "UNAUTHENTICATED", "Missing bearer token.")
    from app.services import voter_service

    claims = voter_service.decode_scoped_token(
        request.app.state.settings, credentials.credentials, expected_scope="voter"
    )
    voter = db.get(Voter, uuid.UUID(claims["vtr"]))
    election = db.get(Election, uuid.UUID(claims["elc"]))
    if voter is None or election is None or voter.election_id != election.id:
        # The token references a session subject that no longer exists: auth failure.
        raise ApiError(401, "UNAUTHENTICATED", "Voter session is no longer valid.")
    return voter, election


def get_election_or_404(
    election_id: uuid.UUID, db: Session = Depends(get_db)
) -> Election:
    election = db.get(Election, election_id)
    if election is None:
        raise ApiError(404, "NOT_FOUND", "Election not found.")
    return election


def get_membership(
    db: Session, organization_id: uuid.UUID, user_id: uuid.UUID
) -> OrgMembership | None:
    return db.scalars(
        select(OrgMembership).where(
            OrgMembership.organization_id == organization_id,
            OrgMembership.user_id == user_id,
        )
    ).first()


def require_organization_organizer(
    organization_id: uuid.UUID,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    membership = get_membership(db, organization_id, user.id)
    if membership is None or membership.role not in ORGANIZER_LEVEL_ROLES:
        raise ApiError(403, "FORBIDDEN", "Organizer role required for this organization.")


def require_election_organizer(
    election: Election = Depends(get_election_or_404),
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Election:
    membership = get_membership(db, election.organization_id, user.id)
    if membership is None or membership.role not in ORGANIZER_LEVEL_ROLES:
        raise ApiError(403, "FORBIDDEN", "Organizer role required for this election.")
    return election


def require_visible_election(
    election: Election = Depends(get_election_or_404),
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Election:
    """Draft elections are organizer-only; open/closed elections are visible to
    any authenticated user (needed for the voting UI)."""
    if election.status == "draft":
        membership = get_membership(db, election.organization_id, user.id)
        if membership is None or membership.role not in ORGANIZER_LEVEL_ROLES:
            raise ApiError(403, "FORBIDDEN", "This election is not open for viewing.")
    return election
