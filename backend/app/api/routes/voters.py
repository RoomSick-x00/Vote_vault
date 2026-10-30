from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_election_organizer
from app.errors import ApiError
from app.models import Election, EligibleVoter
from app.schemas.elections import EligibleVotersAddIn, EligibleVotersOut

router = APIRouter()


@router.post("/{election_id}/eligible-test-voters", status_code=201, response_model=EligibleVotersOut)
def add_eligible_test_voters(
    payload: EligibleVotersAddIn,
    election: Election = Depends(require_election_organizer),
    db: Session = Depends(get_db),
) -> EligibleVotersOut:
    if election.status == "closed":
        raise ApiError(
            409, "ELECTION_CLOSED", "Eligible voters cannot be added after the election is closed."
        )
    existing = set(
        db.scalars(
            select(EligibleVoter.user_id).where(EligibleVoter.election_id == election.id)
        )
    )
    added = skipped = 0
    for user_id in dict.fromkeys(payload.user_ids):  # dedupe, keep order
        if user_id in existing:
            skipped += 1
            continue
        db.add(EligibleVoter(election_id=election.id, user_id=user_id))
        existing.add(user_id)
        added += 1
    db.commit()
    return EligibleVotersOut(
        election_id=str(election.id),
        eligible_test_voters=[{"user_id": str(u)} for u in _ordered(db, election.id)],
        added=added,
        skipped=skipped,
    )


@router.get("/{election_id}/eligible-test-voters", response_model=EligibleVotersOut)
def list_eligible_test_voters(
    election: Election = Depends(require_election_organizer), db: Session = Depends(get_db)
) -> EligibleVotersOut:
    """Organizer-only: the roster is not exposed to other voters."""
    return EligibleVotersOut(
        election_id=str(election.id),
        eligible_test_voters=[{"user_id": str(u)} for u in _ordered(db, election.id)],
    )


def _ordered(db: Session, election_id) -> list:
    return list(
        db.scalars(
            select(EligibleVoter.user_id)
            .where(EligibleVoter.election_id == election_id)
            .order_by(EligibleVoter.created_at)
        )
    )
