"""Organizer roster management: upload (CSV/XLSX), list, delete.

The roster is private organizer data and is never exposed to voters. Upload is
allowed while the election is draft/open; deletion only in draft (identity
stability once voting starts).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_election_organizer
from app.db.base import utcnow
from app.errors import ApiError
from app.models import Ballot, Election, Voter
from app.schemas.voter_flow import VoterImportReportOut, VoterListOut, VoterRecordOut
from app.services import voter_service

router = APIRouter()


@router.post("/{election_id}/voters/upload", response_model=VoterImportReportOut)
def upload_voters(
    election: Election = Depends(require_election_organizer),
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
) -> VoterImportReportOut:
    if election.status in ("closing", "closed"):
        raise ApiError(409, "ELECTION_CLOSED", "The roster cannot be changed after the election closes.")
    content = file.file.read()
    if len(content) > 5 * 1024 * 1024:
        raise ApiError(413, "FILE_TOO_LARGE", "Roster files are limited to 5 MB.")
    report = voter_service.import_roster(db, election, file.filename or "", content)
    return VoterImportReportOut(**report)


@router.get("/{election_id}/voters", response_model=VoterListOut)
def list_voters(
    election: Election = Depends(require_election_organizer), db: Session = Depends(get_db)
) -> VoterListOut:
    voters = list(
        db.scalars(
            select(Voter).where(Voter.election_id == election.id).order_by(Voter.created_at)
        )
    )
    records = [VoterRecordOut(**voter_service.voter_record(v, db)) for v in voters]
    return VoterListOut(voters=records, voterCount=len(records))


@router.delete("/{election_id}/voters/{voter_id}", status_code=204)
def delete_voter(
    election_id: uuid.UUID,
    voter_id: uuid.UUID,
    election: Election = Depends(require_election_organizer),
    db: Session = Depends(get_db),
) -> None:
    if election.status != "draft":
        raise ApiError(409, "ELECTION_NOT_DRAFT", "Roster entries can only be removed while the election is a draft.")
    voter = db.get(Voter, voter_id)
    if voter is None or voter.election_id != election_id:
        raise ApiError(404, "NOT_FOUND", "Roster entry not found.")
    voted = db.scalars(
        select(Ballot.id).where(Ballot.election_id == election_id, Ballot.voter_id == voter_id)
    ).first()
    if voted is not None:
        raise ApiError(409, "VOTER_ALREADY_VOTED", "This voter has already cast a ballot.")
    db.delete(voter)
    db.commit()
