from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_election_organizer, require_visible_election
from app.errors import ApiError
from app.models import Candidate, Election
from app.schemas.elections import CandidateOut, CandidatesAddIn, CandidatesAddOut, CandidatesOut

router = APIRouter()


@router.post("/{election_id}/candidates", status_code=201, response_model=CandidatesAddOut)
def add_candidates(
    payload: CandidatesAddIn,
    election: Election = Depends(require_election_organizer),
    db: Session = Depends(get_db),
) -> CandidatesAddOut:
    if election.status != "draft":
        raise ApiError(
            409, "ELECTION_NOT_DRAFT", "Candidates can only be added while the election is a draft."
        )
    names = [n for n in payload.names if n]
    if not names:
        raise ApiError(422, "VALIDATION_ERROR", "Each candidate needs a non-empty name.")

    existing_names = set(
        db.scalars(select(Candidate.name).where(Candidate.election_id == election.id))
    )
    next_index = (
        db.scalar(
            select(func.max(Candidate.chain_index)).where(Candidate.election_id == election.id)
        )
        or -1
    ) + 1

    added = 0
    skipped = 0
    for name in names:
        if name in existing_names:
            skipped += 1
            continue
        db.add(Candidate(election_id=election.id, name=name, chain_index=next_index))
        existing_names.add(name)
        next_index += 1
        added += 1
    db.commit()
    return CandidatesAddOut(
        election_id=str(election.id),
        candidates=_ordered(db, election.id),
        added=added,
        skipped=skipped,
    )


@router.get("/{election_id}/candidates", response_model=CandidatesOut)
def list_candidates(
    election: Election = Depends(require_visible_election), db: Session = Depends(get_db)
) -> CandidatesOut:
    return CandidatesOut(election_id=str(election.id), candidates=_ordered(db, election.id))


def _ordered(db: Session, election_id: uuid.UUID) -> list[CandidateOut]:
    candidates = db.scalars(
        select(Candidate).where(Candidate.election_id == election_id).order_by(Candidate.chain_index)
    ).all()
    return [CandidateOut.build(c) for c in candidates]
