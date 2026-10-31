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
from app.models import Candidate, Election, PublicationJob, Voter
from app.schemas.elections import (
    CloseElectionOut,
    ElectionCreateIn,
    ElectionListOut,
    ElectionOut,
    OpenElectionOut,
    VoterSchemaIn,
)
from app.services import publication_service, tally_service

router = APIRouter()


@router.get("", response_model=ElectionListOut)
def list_elections(
    user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> ElectionListOut:
    """Dashboard index: elections of organizations the user organizes.

    Scoped to owner/organizer memberships — drafts are organizer-only data, so
    a plain member (voter) gets nothing here; they reach elections by code.
    """
    from app.models import OrgMembership

    org_ids = db.scalars(
        select(OrgMembership.organization_id).where(
            OrgMembership.user_id == user.id, OrgMembership.role.in_(("owner", "organizer"))
        )
    ).all()
    if not org_ids:
        return ElectionListOut(elections=[], electionCount=0)
    elections = db.scalars(
        select(Election)
        .where(Election.organization_id.in_(org_ids))
        .order_by(Election.created_at.desc())
    ).all()
    out = []
    for election in elections:
        candidates = db.scalars(
            select(Candidate)
            .where(Candidate.election_id == election.id)
            .order_by(Candidate.chain_index)
        ).all()
        out.append(ElectionOut.build(election, list(candidates)))
    return ElectionListOut(elections=out, electionCount=len(out))


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
    from app.services.voter_service import generate_election_code, validate_voter_schema

    existing_codes = set(db.scalars(select(Election.code)))
    election = Election(
        organization_id=payload.organization_id,
        title=payload.title,
        description=payload.description,
        code=generate_election_code(existing_codes),
        status="draft",
        # Verification attributes are selected AFTER the roster is uploaded
        # (PUT /voter-schema). Omitted schema stays unset until then.
        voter_schema=(
            validate_voter_schema(payload.voter_schema.model_dump())
            if payload.voter_schema
            else {"identityColumns": [], "otpChannels": []}
        ),
        opens_at=payload.opens_at,
        closes_at=payload.closes_at,
    )
    db.add(election)
    db.flush()
    db.commit()
    db.refresh(election)
    return ElectionOut.build(election, [])


@router.put("/{election_id}/voter-schema", response_model=ElectionOut)
def set_voter_schema(
    payload: VoterSchemaIn,
    election: Election = Depends(require_election_organizer),
    db: Session = Depends(get_db),
) -> ElectionOut:
    """Select verification attributes from the uploaded roster's columns.

    Draft-only (the configuration freezes at open). Validates that every
    roster entry actually has the chosen identity column(s) and the contact
    column for each chosen OTP channel — otherwise some voters could never
    identify themselves.
    """
    if election.status != "draft":
        raise ApiError(409, "ELECTION_NOT_DRAFT", "Verification attributes can only be changed while the election is a draft.")

    from app.services.voter_service import validate_voter_schema

    schema = validate_voter_schema(payload.model_dump())

    voters = list(db.scalars(select(Voter).where(Voter.election_id == election.id)))
    if voters:
        def missing(column: str) -> int:
            return sum(1 for v in voters if not getattr(v, {"rollNo": "roll_no", "name": "name", "email": "email", "phone": "phone"}[column]))

        gaps = [
            f"{column} missing for {missing(column)}/{len(voters)} roster entries"
            for column in schema["identityColumns"] + schema["otpChannels"]
            if missing(column)
        ]
        if gaps:
            raise ApiError(
                422,
                "VALIDATION_ERROR",
                "Cannot verify voters with the selected attributes — " + "; ".join(gaps) + ".",
            )

    election.voter_schema = schema
    db.commit()
    db.refresh(election)
    candidates = db.scalars(select(Candidate).where(Candidate.election_id == election.id).order_by(Candidate.chain_index)).all()
    return ElectionOut.build(election, list(candidates))


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
    election = db.scalars(select(Election).where(Election.id == election.id).with_for_update().execution_options(populate_existing=True)).one()
    if election.status == "open":
        raise ApiError(409, "ELECTION_NOT_DRAFT", "Election is already open.")
    if election.status in ("closing", "closed"):
        raise ApiError(409, "ELECTION_NOT_DRAFT", "Election is closed and can no longer be opened.")

    candidate_count = db.scalar(
        select(func.count(Candidate.id)).where(Candidate.election_id == election.id)
    )
    if not candidate_count:
        raise ApiError(409, "ELECTION_HAS_NO_CANDIDATES", "Add at least one candidate before opening.")
    voter_count = db.scalar(select(func.count(Voter.id)).where(Voter.election_id == election.id))
    if not voter_count:
        raise ApiError(409, "ELECTION_HAS_NO_VOTERS", "Upload a voter roster before opening.")

    from app.services.voter_service import validate_voter_schema

    validate_voter_schema(election.voter_schema or {})  # 422 if verification attributes were never selected

    from app.services.configuration import freeze_configuration
    frozen = freeze_configuration(db, election)
    _ensure_job(db, election, "register_election", settings, payload={
        **publication_service.build_payload("register_election", election.id, config_hash=frozen["config_hash"]), **frozen})
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
    election = db.scalars(select(Election).where(Election.id == election.id).with_for_update().execution_options(populate_existing=True)).one()
    if election.status in ("closing", "closed"):  # idempotent: repeated close returns same state
        return CloseElectionOut(
            election_id=str(election.id), status=election.status, closed_at=election.closed_at
        )
    if election.status != "open":
        raise ApiError(409, "ELECTION_NOT_OPEN", "Only an open election can be closed.")

    result_hash = tally_service.compute_result_hash(db, election)
    election.status = "closing"
    election.closed_at = None
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


@router.get("/{election_id}/configuration")
def get_configuration(election: Election = Depends(require_visible_election), db: Session = Depends(get_db)):
    job = db.scalars(select(PublicationJob).where(PublicationJob.election_id == election.id, PublicationJob.job_type == "register_election")).first()
    if job is None or "configuration" not in job.payload:
        raise ApiError(409, "CONFIGURATION_NOT_FROZEN", "Configuration is frozen at opening.")
    return {key: job.payload[key] for key in ("configuration", "canonical_json", "config_hash")}
