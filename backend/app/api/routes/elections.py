"""Election lifecycle: create (draft) -> open -> close.

Every lifecycle transition also writes its BallotRegistry publication job in
the SAME transaction as the status change; the chain submission itself happens
later and independently (see services/publication_service.py).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_db,
    get_membership,
    get_settings,
    require_election_organizer,
    require_visible_election,
)
from app.auth.tokens import AuthUser
from app.config import Settings
from app.db.base import utcnow
from app.errors import ApiError
from app.models import Candidate, Election, EligibleVoter, PublicationJob
from app.schemas.elections import (
    CloseElectionOut,
    ElectionCreateIn,
    ElectionOut,
    OpenElectionOut,
)
from app.services import publication_service, tally_service

router = APIRouter()


@router.post("", status_code=201, response_model=ElectionOut)
def create_election(
    payload: ElectionCreateIn,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ElectionOut:
    membership = get_membership(db, payload.organization_id, user.id)
    if membership is None or membership.role not in ("owner", "organizer"):
        raise ApiError(403, "FORBIDDEN", "Organizer role required for this organization.")
    election = Election(
        organization_id=payload.organization_id,
        title=payload.title,
        status="draft",
        opens_at=payload.opens_at,
        closes_at=payload.closes_at,
    )
    db.add(election)
    db.flush()
    publication_service.create_job(
        db,
        job_type="register_election",
        election=election,
        payload=publication_service.build_payload("register_election", election.id),
        max_attempts=settings.publication_max_attempts,
    )
    db.commit()
    db.refresh(election)
    return ElectionOut.build(election, [])


@router.get("/{election_id}", response_model=ElectionOut)
def get_election(
    election: Election = Depends(require_visible_election), db: Session = Depends(get_db)
) -> ElectionOut:
    candidates = _ordered_candidates(db, election.id)
    return ElectionOut.build(election, candidates)


@router.post("/{election_id}/open", response_model=OpenElectionOut)
def open_election(
    election: Election = Depends(require_election_organizer),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> OpenElectionOut:
    if election.status == "open":
        raise ApiError(409, "ELECTION_NOT_DRAFT", "Election is already open.")
    if election.status == "closed":
        raise ApiError(409, "ELECTION_NOT_DRAFT", "Election is closed and can no longer be opened.")

    candidate_count = db.scalar(
        select(func.count(Candidate.id)).where(Candidate.election_id == election.id)
    )
    if not candidate_count:
        raise ApiError(409, "ELECTION_HAS_NO_CANDIDATES", "Add at least one candidate before opening.")
    voter_count = db.scalar(
        select(func.count(EligibleVoter.id)).where(EligibleVoter.election_id == election.id)
    )
    if not voter_count:
        raise ApiError(409, "ELECTION_HAS_NO_VOTERS", "Add at least one eligible voter before opening.")

    election.status = "open"
    election.opened_at = utcnow()
    _ensure_job(db, election, "open_election", settings)
    db.commit()
    db.refresh(election)
    return OpenElectionOut(
        election_id=str(election.id), status=election.status, opened_at=election.opened_at
    )


@router.post("/{election_id}/close", response_model=CloseElectionOut)
def close_election(
    election: Election = Depends(require_election_organizer),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CloseElectionOut:
    if election.status == "closed":  # idempotent: repeated close returns same state
        return CloseElectionOut(
            election_id=str(election.id), status=election.status, closed_at=election.closed_at
        )
    if election.status != "open":
        raise ApiError(409, "ELECTION_NOT_OPEN", "Only an open election can be closed.")

    result_hash = tally_service.compute_result_hash(db, election)
    election.status = "closed"
    election.closed_at = utcnow()
    _ensure_job(db, election, "close_election", settings)
    _ensure_job(
        db,
        election,
        "publish_result",
        settings,
        payload=publication_service.build_payload(
            "publish_result", election.id, result_hash=result_hash
        ),
    )
    db.commit()
    db.refresh(election)
    return CloseElectionOut(
        election_id=str(election.id), status=election.status, closed_at=election.closed_at
    )


def _ordered_candidates(db: Session, election_id) -> list[Candidate]:
    return list(
        db.scalars(
            select(Candidate).where(Candidate.election_id == election_id).order_by(Candidate.chain_index)
        )
    )


def _ensure_job(
    db: Session,
    election: Election,
    job_type: str,
    settings: Settings,
    payload: dict | None = None,
) -> None:
    """Create the lifecycle job once (close is idempotent, so must job creation be)."""
    existing = db.scalars(
        select(PublicationJob).where(
            PublicationJob.election_id == election.id,
            PublicationJob.job_type == job_type,
            PublicationJob.ballot_id.is_(None),
        )
    ).first()
    if existing is not None:
        return
    publication_service.create_job(
        db,
        job_type=job_type,
        election=election,
        payload=payload
        or publication_service.build_payload(job_type, election.id),
        max_attempts=settings.publication_max_attempts,
    )
