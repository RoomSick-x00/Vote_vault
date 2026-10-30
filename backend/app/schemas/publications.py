from __future__ import annotations

from app.models import PublicationJob
from app.schemas.common import APIModel, UtcIso


class PublicationJobOut(APIModel):
    """Organizer-facing job view. Deliberately excludes any voter identity —
    jobs are keyed by receipt (ballot) id only."""

    job_id: str
    job_type: str
    receipt_id: str | None = None
    status: str
    attempts: int
    max_attempts: int
    transaction_hash: str | None = None
    block_number: int | None = None
    next_attempt_at: UtcIso | None = None
    last_error: str | None = None
    created_at: UtcIso
    confirmed_at: UtcIso | None = None

    @classmethod
    def build(cls, job: PublicationJob) -> "PublicationJobOut":
        return cls(
            job_id=str(job.id),
            job_type=job.job_type,
            receipt_id=str(job.ballot_id) if job.ballot_id else None,
            status=job.status,
            attempts=job.attempts,
            max_attempts=job.max_attempts,
            transaction_hash=job.tx_hash,
            block_number=job.block_number,
            next_attempt_at=job.next_attempt_at,
            last_error=job.last_error,
            created_at=job.created_at,
            confirmed_at=job.confirmed_at,
        )


class PublicationsOut(APIModel):
    election_id: str
    publications: list[PublicationJobOut]
    summary: dict[str, int]


class RetryOut(APIModel):
    election_id: str
    requeued: int
    processed: dict[str, int]
