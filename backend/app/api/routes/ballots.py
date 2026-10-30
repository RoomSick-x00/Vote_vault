from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_settings
from app.auth.tokens import AuthUser
from app.config import Settings
from app.errors import ApiError
from app.schemas.ballots import BallotAcceptedOut, BallotSubmitIn, ReceiptOut
from app.services import ballot_service, publication_service

router = APIRouter()


@router.post("/{election_id}/ballots", status_code=202, response_model=BallotAcceptedOut)
def submit_ballot(
    election_id: uuid.UUID,
    payload: BallotSubmitIn,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> BallotAcceptedOut:
    """Submit one ballot for the logged-in eligible voter.

    Identity comes from the token; a voter id in the body would be ignored.
    Returns the existing receipt for an identical retry (idempotent); a second,
    different choice is rejected. 202 means accepted for processing — it is NOT
    proof of on-chain recording; check the receipt endpoint for that.
    """
    submission = ballot_service.submit_ballot(
        db,
        election_id=election_id,
        voter_id=user.id,
        candidate_id=payload.candidate_id,
        settings=settings,
    )
    return BallotAcceptedOut.build(
        submission.ballot, submission.job, idempotent_retry=submission.idempotent_retry
    )


@router.get("/{election_id}/receipts/{receipt_id}", response_model=ReceiptOut)
def get_receipt(
    election_id: uuid.UUID,
    receipt_id: uuid.UUID,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReceiptOut:
    ballot = publication_service.require_ballot_of_election(db, receipt_id, election_id)
    if ballot.voter_id != user.id:
        raise ApiError(403, "FORBIDDEN", "Receipts are visible only to the submitting voter.")
    job = publication_service.get_ballot_job(db, ballot.id)
    if job is None:  # pragma: no cover - job is written atomically with the ballot
        raise ApiError(500, "PUBLICATION_JOB_MISSING", "Ballot has no publication job.")
    return ReceiptOut.build(ballot, job)
