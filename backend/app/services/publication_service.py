"""Publication job processing: database jobs -> BallotRegistry transactions.

Design (agreed with the blockchain teammate):
- A job row is created in the same DB transaction as the state change it
  anchors. Submission to the chain is a SEPARATE operation with retries.
- `pending`   = accepted / submitted / scheduled for retry — not yet proven.
- `confirmed` = transaction receipt status 1 AND the expected event present in
  the receipt logs with arguments equal to the submitted values, on the
  configured chain id.
- `failed`    = reverted/absent event and attempts exhausted, or operator-given
  up. Failures before exhaustion stay `pending` with a backoff.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.blockchain.publisher import ChainError, ChainPublisher, ChainReceipt
from app.config import Settings
from app.db.base import utcnow
from app.errors import ApiError
from app.eth_events import EVENT_SIGNATURES, find_matching_event_log
from app.models import Ballot, Election, PublicationJob

# Payload argument names per job type, in Solidity argument order.
JOB_ARG_ORDER: dict[str, list[str]] = {
    "register_election": ["election_id", "config_hash"],
    "open_election": ["election_id"],
    "publish_ballot": ["election_id", "ballot_id", "commitment"],
    "close_election": ["election_id"],
    "publish_result": ["election_id", "result_hash"],
}


def build_payload(job_type: str, election_id: uuid.UUID, **extra: str) -> dict:
    """Canonical 0x-hex payload for a job, using the agreed ID encoding."""
    from app.services.ids import uuid_to_bytes32_hex

    payload: dict[str, str] = {"election_id": uuid_to_bytes32_hex(election_id)}
    for key in JOB_ARG_ORDER[job_type][1:]:
        if key not in extra:
            raise ValueError(f"payload for {job_type} requires {key!r}")
        payload[key] = extra[key]
    return payload


def create_job(
    db: Session,
    *,
    job_type: str,
    election: Election,
    payload: dict,
    ballot_id: uuid.UUID | None = None,
    max_attempts: int,
) -> PublicationJob:
    job = PublicationJob(
        job_type=job_type,
        election_id=election.id,
        ballot_id=ballot_id,
        payload=payload,
        status="pending",
        attempts=0,
        max_attempts=max_attempts,
    )
    db.add(job)
    return job


def get_ballot_job(db: Session, ballot_id: uuid.UUID) -> PublicationJob | None:
    return db.scalars(
        select(PublicationJob).where(
            PublicationJob.ballot_id == ballot_id,
            PublicationJob.job_type == "publish_ballot",
        )
    ).first()


def _process_due_jobs(
    session_factory: sessionmaker[Session],
    publisher: ChainPublisher,
    settings: Settings,
    limit: int = 50,
) -> dict[str, int]:
    """Process pending jobs whose backoff has elapsed. Returns an outcome summary."""
    summary = {"confirmed": 0, "retry_scheduled": 0, "failed": 0}
    now = utcnow()
    with session_factory() as db:
        jobs = db.scalars(
            select(PublicationJob)
            .where(
                PublicationJob.status == "pending",
                PublicationJob.attempts < PublicationJob.max_attempts,
                or_(
                    PublicationJob.next_attempt_at.is_(None),
                    PublicationJob.next_attempt_at <= now,
                ),
            )
            .order_by(PublicationJob.created_at)
        ).all()
        attempted = 0
        for job in jobs:
            if attempted >= limit:
                break
            if not dependencies_confirmed(db, job):
                continue
            attempted += 1
            outcome = attempt_job(db, job, publisher, settings)
            summary[outcome] += 1
    return summary


def attempt_job(
    db: Session, job: PublicationJob, publisher: ChainPublisher, settings: Settings
) -> str:
    """Run one attempt; commits after every state transition so a crash loses nothing."""
    if not dependencies_confirmed(db, job):
        return "retry_scheduled"
    now = utcnow()
    job.attempts += 1
    db.commit()  # the attempt itself is audit state, persist it before sending

    try:
        tx_hash = publisher.submit(job.job_type, job.payload)
    except ChainError as exc:
        return _record_failure(db, job, settings, exc, utcnow())

    job.tx_hash = tx_hash
    job.submitted_at = utcnow()
    db.commit()

    try:
        receipt = publisher.fetch_receipt(
            tx_hash,
            timeout=settings.publication_receipt_timeout_seconds,
            confirmations=settings.publication_confirmations,
        )
        _verify_receipt(job, receipt)
    except ChainError as exc:
        return _record_failure(db, job, settings, exc, utcnow())

    job.status = "confirmed"
    job.block_number = receipt.block_number
    job.confirmed_at = utcnow()
    job.last_error = None
    if job.job_type == "close_election":
        election = db.get(Election, job.election_id)
        election.status = "closed"
        election.closed_at = utcnow()
    db.commit()
    return "confirmed"


def _record_failure(
    db: Session, job: PublicationJob, settings: Settings, error: ChainError, now: datetime
) -> str:
    job.last_error = str(error)[:2000]
    if job.attempts >= job.max_attempts:
        job.status = "failed"
        job.next_attempt_at = None
        outcome = "failed"
    else:
        job.status = "pending"
        delay = settings.publication_retry_delay_seconds * (2 ** (job.attempts - 1))
        job.next_attempt_at = now + timedelta(seconds=delay)
        outcome = "retry_scheduled"
    db.commit()
    return outcome


def _verify_receipt(job: PublicationJob, receipt: ChainReceipt) -> None:
    if receipt.status != 1:
        raise ChainError(f"transaction {job.tx_hash} reverted on chain (status {receipt.status})")
    signature = EVENT_SIGNATURES[job.job_type]
    expected_topics = _expected_topics(job)
    expected_data = _expected_data_word(job)
    log = find_matching_event_log(receipt.logs, signature, expected_topics, expected_data)
    if log is None:
        raise ChainError(
            f"expected event {signature} with matching args not found in receipt "
            f"logs of {job.tx_hash} ({len(receipt.logs)} logs)"
        )


def _expected_topics(job: PublicationJob) -> list[bytes]:
    """Event topics that must match, in order: [signature, electionId, ballotId?]."""
    election_b32 = _hex_to_bytes(job.payload["election_id"])
    topics = [election_b32]
    if job.job_type == "publish_ballot":
        topics.append(_hex_to_bytes(job.payload["ballot_id"]))
    return topics


def _expected_data_word(job: PublicationJob) -> bytes | None:
    if job.job_type == "register_election":
        return _hex_to_bytes(job.payload["config_hash"])
    if job.job_type == "publish_ballot":
        return _hex_to_bytes(job.payload["commitment"])
    if job.job_type == "publish_result":
        return _hex_to_bytes(job.payload["result_hash"])
    return None


def _hex_to_bytes(value: str) -> bytes:
    return bytes.fromhex(value[2:] if value.startswith("0x") else value)


def requeue_election_jobs(db: Session, election_id: uuid.UUID) -> int:
    """Operator retry: give exhausted/failed jobs a fresh budget and make all
    pending jobs immediately due. Idempotent to call; safe because the contract
    functions are idempotent and receipts are verified per attempt."""
    jobs = db.scalars(
        select(PublicationJob).where(
            PublicationJob.election_id == election_id,
            PublicationJob.status != "confirmed",
        )
    ).all()
    for job in jobs:
        job.status = "pending"
        job.next_attempt_at = utcnow()
        if job.attempts >= job.max_attempts:
            job.attempts = 0
    db.commit()
    return len(jobs)


def publications_summary(db: Session, election_id: uuid.UUID) -> dict[str, int]:
    jobs = db.scalars(
        select(PublicationJob).where(PublicationJob.election_id == election_id)
    ).all()
    summary = {"pending": 0, "confirmed": 0, "failed": 0}
    for job in jobs:
        summary[job.status] += 1
    return summary


def result_publication_status(db: Session, election_id: uuid.UUID) -> str:
    """Status of the publish_result job: confirmed | pending | failed | not_published."""
    job = db.scalars(
        select(PublicationJob)
        .where(
            PublicationJob.election_id == election_id,
            PublicationJob.job_type == "publish_result",
        )
    ).first()
    if job is None:
        return "not_published"
    return job.status


def require_ballot_of_election(db: Session, ballot_id: uuid.UUID, election_id: uuid.UUID) -> Ballot:
    ballot = db.get(Ballot, ballot_id)
    if ballot is None or ballot.election_id != election_id:
        raise ApiError(404, "NOT_FOUND", "Receipt not found for this election.")
    return ballot


def dependencies_confirmed(db: Session, job: PublicationJob) -> bool:
    """Do not spend attempts on blocked jobs; failed prerequisites remain visible."""
    jobs = list(db.scalars(select(PublicationJob).where(PublicationJob.election_id == job.election_id)))
    def confirmed(kind):
        rows = [j for j in jobs if j.job_type == kind]
        return bool(rows) and all(j.status == "confirmed" for j in rows)
    if job.job_type == "register_election":
        return bool(job.payload.get("config_hash"))
    if job.job_type == "open_election":
        return confirmed("register_election")
    if job.job_type == "publish_ballot":
        return confirmed("open_election")
    if job.job_type == "close_election":
        if not confirmed("open_election"):
            return False
        ballots = list(db.scalars(select(Ballot).where(Ballot.election_id == job.election_id, Ballot.accepted.is_(True))))
        return all(any(j.ballot_id == b.id and j.job_type == "publish_ballot" and j.status == "confirmed" for j in jobs) for b in ballots)
    if job.job_type == "publish_result":
        return confirmed("close_election")
    return False


# Single signer: serialize processing across threads and PostgreSQL worker processes.
# Session-level advisory lock uses a dedicated connection so per-job commits do not release it.
from threading import Lock
_publisher_lock = Lock()


def process_due_jobs(session_factory, publisher, settings, limit=50):
    with _publisher_lock:
        engine = session_factory.kw["bind"]
        if engine.dialect.name != "postgresql":
            return _process_due_jobs(session_factory, publisher, settings, limit)
        from sqlalchemy import text
        with engine.connect() as lock_connection:
            acquired = lock_connection.scalar(text("SELECT pg_try_advisory_lock(867530931337)"))
            if not acquired:
                return {"confirmed": 0, "retry_scheduled": 0, "failed": 0}
            try:
                return _process_due_jobs(session_factory, publisher, settings, limit)
            finally:
                lock_connection.execute(text("SELECT pg_advisory_unlock(867530931337)"))
