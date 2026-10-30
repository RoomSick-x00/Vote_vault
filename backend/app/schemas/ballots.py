from __future__ import annotations

import uuid

from pydantic import Field

from app.models import Ballot, PublicationJob
from app.schemas.common import APIModel, UtcIso


class BallotSubmitIn(APIModel):
    candidate_id: uuid.UUID


class BallotAcceptedOut(APIModel):
    election_id: str
    receipt_id: str
    status: str  # publication status snapshot: pending | confirmed | failed
    candidate_id: str
    submitted_at: UtcIso
    idempotent_retry: bool = False

    @classmethod
    def build(cls, ballot: Ballot, job: PublicationJob, *, idempotent_retry: bool) -> "BallotAcceptedOut":
        return cls(
            election_id=str(ballot.election_id),
            receipt_id=str(ballot.id),
            status=job.status,
            candidate_id=str(ballot.candidate_id),
            submitted_at=ballot.submitted_at,
            idempotent_retry=idempotent_retry,
        )


class ReceiptOut(APIModel):
    election_id: str
    receipt_id: str
    status: str  # pending | confirmed | failed
    ballot_accepted: bool
    candidate_id: str
    commitment: str
    nonce: str  # 0x + 64 hex; lets the voter recompute the commitment later
    transaction_hash: str | None = None
    block_number: int | None = None
    submitted_at: UtcIso | None = None
    confirmed_at: UtcIso | None = None
    error: str | None = Field(default=None, description="Last publication error, if any")

    @classmethod
    def build(cls, ballot: Ballot, job: PublicationJob) -> "ReceiptOut":
        return cls(
            election_id=str(ballot.election_id),
            receipt_id=str(ballot.id),
            status=job.status,
            ballot_accepted=ballot.accepted,
            candidate_id=str(ballot.candidate_id),
            commitment=ballot.commitment,
            nonce="0x" + ballot.nonce,
            transaction_hash=job.tx_hash,
            block_number=job.block_number,
            submitted_at=job.submitted_at or ballot.submitted_at,
            confirmed_at=job.confirmed_at,
            error=job.last_error,
        )
