"""Public voter flow (no accounts): code -> identify -> OTP -> session -> ballot.

Wire shapes are camelCase, matching the frontend types. Voter sessions are
short-lived backend-issued tokens (scope "voter"); organizer/Supabase tokens
are rejected here and voter tokens are rejected everywhere else. OTP codes are
stored hashed; in non-production environments the code is returned in the
response (dev delivery) because no mail/SMS provider is wired.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings, get_voter_session
from app.config import Settings
from app.errors import ApiError
from app.models import Election, Voter
from app.schemas.voter_flow import (
    BallotReceiptOut,
    BallotVoteIn,
    IdentifyIn,
    IdentifyOut,
    OtpRequestIn,
    OtpRequestOut,
    OtpVerifyIn,
    PublicElectionOut,
    VerifiedVoterOut,
    VoterSessionOut,
)
from app.services import ballot_service, voter_service

router = APIRouter()


@router.get("/vote/session", response_model=VoterSessionOut)
def voter_session(
    session: tuple[Voter, Election] = Depends(get_voter_session), db: Session = Depends(get_db)
) -> VoterSessionOut:
    voter, election = session
    return VoterSessionOut(**voter_service.voter_session_info(db, election, voter))


@router.get("/vote/receipt", response_model=BallotReceiptOut)
def voter_receipt(
    session: tuple[Voter, Election] = Depends(get_voter_session), db: Session = Depends(get_db)
) -> ReceiptOut:
    voter, election = session
    from sqlalchemy import select as sa_select

    from app.models import Ballot
    from app.services import publication_service

    ballot = db.scalars(
        sa_select(Ballot).where(
            Ballot.election_id == election.id, Ballot.voter_id == voter.id, Ballot.accepted.is_(True)
        )
    ).first()
    if ballot is None:
        raise ApiError(404, "NOT_FOUND", "No ballot submitted yet.")
    job = publication_service.get_ballot_job(db, ballot.id)
    if job is None:  # pragma: no cover - job is atomic with the ballot
        raise ApiError(500, "PUBLICATION_JOB_MISSING", "Ballot has no publication job.")
    return BallotReceiptOut(
        receiptId=str(ballot.id),
        electionId=str(election.id),
        candidateId=str(ballot.candidate_id),
        commitment=ballot.commitment,
        status=job.status,
        txHash=job.tx_hash,
        blockNumber=job.block_number,
        createdAt=ballot.submitted_at.isoformat(timespec="seconds") + "Z",
        confirmedAt=job.confirmed_at.isoformat(timespec="seconds") + "Z" if job.confirmed_at else None,
    )


@router.get("/vote/{code}", response_model=PublicElectionOut)
def public_election(code: str, db: Session = Depends(get_db)) -> PublicElectionOut:
    election = db.scalars(select(Election).where(Election.code == code.strip().upper())).first()
    if election is None or election.status == "draft":
        raise ApiError(404, "NOT_FOUND", "No open election with this code.")
    return PublicElectionOut(**voter_service.public_election(election))


@router.post("/vote/{code}/identify", response_model=IdentifyOut)
def identify(
    code: str, payload: IdentifyIn, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> IdentifyOut:
    election = db.scalars(select(Election).where(Election.code == code.strip().upper())).first()
    if election is None or election.status == "draft":
        raise ApiError(404, "NOT_FOUND", "No open election with this code.")
    if election.status != "open":
        raise ApiError(409, "ELECTION_NOT_OPEN", "This election is not accepting voters.")
    voter_service.check_voting_window(election)
    voter = voter_service.match_voter(db, election, payload.model_dump())
    token = voter_service.mint_identify_token(settings, election, voter)
    return IdentifyOut(
        identifyToken=token,
        channels=list((election.voter_schema or {}).get("otpChannels", [])),
    )


@router.post("/vote/otp/request", response_model=OtpRequestOut)
def request_otp(
    payload: OtpRequestIn, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> OtpRequestOut:
    claims = voter_service.decode_scoped_token(settings, payload.identifyToken, expected_scope="identify")
    election = db.get(Election, uuid.UUID(claims["elc"]))
    voter = db.get(Voter, uuid.UUID(claims["vtr"]))
    if election is None or voter is None or voter.election_id != election.id:
        raise ApiError(404, "NOT_FOUND", "Identify session is no longer valid.")
    if payload.channel not in (election.voter_schema or {}).get("otpChannels", []):
        raise ApiError(422, "VALIDATION_ERROR", f"Channel '{payload.channel}' is not enabled for this election.")
    _, dev_code = voter_service.create_otp_challenge(
        db, settings, election, voter, claims["jti"], payload.channel, payload.contact
    )
    return OtpRequestOut(
        resendAfter=voter_service.OTP_RESEND_AFTER_SECONDS,
        expiresIn=voter_service.OTP_TTL_SECONDS,
        channel=payload.channel,
        devCode=dev_code,
    )


@router.post("/vote/otp/verify", response_model=VerifiedVoterOut)
def verify_otp(
    payload: OtpVerifyIn, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> VerifiedVoterOut:
    claims = voter_service.decode_scoped_token(settings, payload.identifyToken, expected_scope="identify")
    voter, election = voter_service.consume_otp(db, settings, claims, payload.otp)
    token = voter_service.mint_voter_session(settings, election, voter)
    return VerifiedVoterOut(token=token, session=VoterSessionOut(**voter_service.voter_session_info(db, election, voter)))


@router.post("/vote/ballot", status_code=202, response_model=BallotReceiptOut)
def submit_ballot_flow(
    payload: BallotVoteIn,
    session: tuple[Voter, Election] = Depends(get_voter_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> BallotReceiptOut:
    voter, election = session
    try:
        candidate_id = uuid.UUID(payload.candidateId)
    except ValueError as exc:
        raise ApiError(422, "VALIDATION_ERROR", "candidateId must be a UUID.") from exc
    submission = ballot_service.submit_ballot(
        db,
        election_id=election.id,
        voter_id=voter.id,
        candidate_id=candidate_id,
        settings=settings,
    )
    job = submission.job
    return BallotReceiptOut(
        receiptId=str(submission.ballot.id),
        electionId=str(election.id),
        candidateId=str(submission.ballot.candidate_id),
        commitment=submission.ballot.commitment,
        status=job.status,
        txHash=job.tx_hash,
        blockNumber=job.block_number,
        createdAt=submission.ballot.submitted_at.isoformat(timespec="seconds") + "Z",
        confirmedAt=job.confirmed_at.isoformat(timespec="seconds") + "Z" if job.confirmed_at else None,
    )


