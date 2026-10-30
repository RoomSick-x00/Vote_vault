from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_election_organizer
from app.models import Election, PublicationJob
from app.schemas.publications import PublicationJobOut, PublicationsOut, RetryOut
from app.services import publication_service

router = APIRouter()


@router.get("/{election_id}/publications", response_model=PublicationsOut)
def list_publications(
    election: Election = Depends(require_election_organizer), db: Session = Depends(get_db)
) -> PublicationsOut:
    """Blockchain publication status for every job of this election.

    Honest two-phase state: `pending` (submitted/scheduled, not proven),
    `confirmed` (receipt + matching event), `failed` (reverted or retries
    exhausted). The database and the chain share no transaction.
    """
    jobs = db.scalars(
        select(PublicationJob)
        .where(PublicationJob.election_id == election.id)
        .order_by(PublicationJob.created_at)
    ).all()
    return PublicationsOut(
        election_id=str(election.id),
        publications=[PublicationJobOut.build(job) for job in jobs],
        summary=publication_service.publications_summary(db, election.id),
    )


@router.post("/{election_id}/publications/retry", response_model=RetryOut)
def retry_publications(
    request: Request,
    election: Election = Depends(require_election_organizer),
    db: Session = Depends(get_db),
) -> RetryOut:
    """Operator retry: requeue unconfirmed jobs with a fresh attempt budget and
    process them now. Safe because the contract functions are idempotent and
    every attempt is receipt-verified."""
    requeued = publication_service.requeue_election_jobs(db, election.id)
    processed = publication_service.process_due_jobs(
        request.app.state.sessionmaker, request.app.state.publisher, request.app.state.settings
    )
    return RetryOut(election_id=str(election.id), requeued=requeued, processed=processed)
