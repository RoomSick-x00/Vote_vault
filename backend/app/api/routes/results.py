from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_election_organizer
from app.errors import ApiError
from app.models import Election
from app.schemas.results import ResultCountOut, ResultsOut
from app.services import publication_service, tally_service

router = APIRouter()


@router.get("/{election_id}/results", response_model=ResultsOut)
def get_results(
    election: Election = Depends(require_election_organizer), db: Session = Depends(get_db)
) -> ResultsOut:
    """Backend demo tally, organizer-only, after close.

    This tally is computed directly from the ballots table. It is NOT an
    independently verified result; the disclaimer field travels with every
    response and must be shown as-is in the UI.
    """
    if election.status != "closed":
        raise ApiError(409, "ELECTION_NOT_CLOSED", "Results are available after the election is closed.")
    tally = tally_service.compute_tally(db, election)
    return ResultsOut(
        election_id=str(election.id),
        status=election.status,
        tally_type=tally_service.TALLY_TYPE,
        total_ballots=tally["total_ballots"],
        counts=[ResultCountOut(**row) for row in tally["counts"]],
        publications=publication_service.publications_summary(db, election.id),
        published_result_status=publication_service.result_publication_status(db, election.id),
        disclaimer=tally_service.TALLY_DISCLAIMER,
    )
