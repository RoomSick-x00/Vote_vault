import uuid
from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_election_or_404, get_settings
from app.errors import ApiError
from app.models import Election
from app.services.audit import export_record, verify_record

router = APIRouter()

@router.get("/{election_id}")
def get_audit(election: Election = Depends(get_election_or_404), db: Session = Depends(get_db)):
    if election.status == "draft":
        raise ApiError(404, "NOT_FOUND", "Public records are available after opening.")
    return export_record(db, election)

@router.post("/verify")
def verify_audit(record: dict = Body(...), settings=Depends(get_settings)):
    return {"checks": verify_record(record, settings)}
