"""Ballot submission: all voting rules enforced here, races settled by the database.

Rules on every submission:
  1. Election exists; status `open`; within the opens_at/closes_at window.
  2. The token-derived user is in eligible_voters for this election.
  3. The candidate belongs to this election.
  4. One accepted ballot per (election, voter): enforced by a unique constraint
     inside a single transaction, so simultaneous requests cannot both win.
     - identical retry (same voter, same candidate) -> the existing receipt.
     - a different second choice -> 409 DUPLICATE_VOTE; the original stands.

The ballot and its publish_ballot publication job are written in the SAME
transaction; chain submission happens later and independently.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.base import utcnow
from app.errors import ApiError
from app.models import Ballot, Candidate, Election, EligibleVoter, PublicationJob
from app.services import publication_service
from app.services.commitment import make_ballot_commitment


@dataclass
class BallotSubmission:
    ballot: Ballot
    job: PublicationJob
    idempotent_retry: bool


def submit_ballot(
    db: Session,
    *,
    election_id: uuid.UUID,
    voter_id: uuid.UUID,
    candidate_id: uuid.UUID,
    settings: Settings,
) -> BallotSubmission:
    election = db.get(Election, election_id)
    if election is None:
        raise ApiError(404, "NOT_FOUND", "Election not found.")

    # Deduplicate BEFORE validation: an identical retry after close must still
    # return the existing receipt, not ELECTION_CLOSED.
    existing = _find_ballot(db, election_id, voter_id)
    if existing is not None:
        return _settle_existing(db, existing, candidate_id)

    candidate = _validate_submission(db, election, voter_id, candidate_id)

    commitment_hex, nonce_hex = make_ballot_commitment(
        election_id=election.id,
        candidate_chain_index=candidate.chain_index,
    )

    ballot = Ballot(
        election_id=election.id,
        voter_id=voter_id,
        candidate_id=candidate.id,
        nonce=nonce_hex,
        commitment=commitment_hex,
        accepted=True,
        submitted_at=utcnow(),
    )
    db.add(ballot)
    try:
        db.flush()  # ballot.id assigned here; the INSERT races on the unique constraint
        from app.services.ids import uuid_to_bytes32_hex

        job = publication_service.create_job(
            db,
            job_type="publish_ballot",
            election=election,
            payload=publication_service.build_payload(
                "publish_ballot",
                election.id,
                ballot_id=uuid_to_bytes32_hex(ballot.id),
                commitment=commitment_hex,
            ),
            ballot_id=ballot.id,
            max_attempts=settings.publication_max_attempts,
        )
        db.commit()
    except IntegrityError:
        # A concurrent request won the unique (election_id, voter_id) race.
        db.rollback()
        existing = _find_ballot(db, election_id, voter_id)
        if existing is None:  # pragma: no cover - constraint fired for another pair
            raise ApiError(409, "DUPLICATE_VOTE", "A ballot has already been submitted.")
        return _settle_existing(db, existing, candidate_id)

    return BallotSubmission(ballot=ballot, job=job, idempotent_retry=False)


def _find_ballot(db: Session, election_id: uuid.UUID, voter_id: uuid.UUID) -> Ballot | None:
    return db.scalars(
        select(Ballot).where(Ballot.election_id == election_id, Ballot.voter_id == voter_id)
    ).first()


def _settle_existing(db: Session, existing: Ballot, candidate_id: uuid.UUID) -> BallotSubmission:
    if existing.candidate_id != candidate_id:
        raise ApiError(
            409,
            "DUPLICATE_VOTE",
            "A ballot has already been submitted for a different candidate; "
            "the original ballot stands.",
        )
    job = publication_service.get_ballot_job(db, existing.id)
    if job is None:  # pragma: no cover - job is written atomically with the ballot
        raise ApiError(500, "PUBLICATION_JOB_MISSING", "Ballot has no publication job.")
    return BallotSubmission(ballot=existing, job=job, idempotent_retry=True)


def _validate_submission(
    db: Session, election: Election, voter_id: uuid.UUID, candidate_id: uuid.UUID
) -> Candidate:
    now = utcnow()
    if election.status == "draft":
        raise ApiError(409, "ELECTION_NOT_OPEN", "This election is not open for voting.")
    if election.status == "closed":
        raise ApiError(409, "ELECTION_CLOSED", "This election is closed.")
    if election.opens_at is not None and now < election.opens_at:
        raise ApiError(409, "ELECTION_NOT_OPEN", "The voting window has not opened yet.")
    if election.closes_at is not None and now > election.closes_at:
        raise ApiError(409, "ELECTION_CLOSED", "The voting window has closed.")

    eligible = db.scalars(
        select(EligibleVoter).where(
            EligibleVoter.election_id == election.id, EligibleVoter.user_id == voter_id
        )
    ).first()
    if eligible is None:
        raise ApiError(403, "NOT_ELIGIBLE", "You are not an eligible voter for this election.")

    candidate = db.get(Candidate, candidate_id)
    if candidate is None or candidate.election_id != election.id:
        raise ApiError(422, "INVALID_CANDIDATE", "Candidate does not belong to this election.")
    return candidate
