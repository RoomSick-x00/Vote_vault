"""Backend demo tally and the anchored result hash.

The tally counts accepted ballots directly from the database. It is a demo
convenience for the organizer — NOT an independently verified tally — and every
surface that exposes it carries the disclaimer:
    "backend demo tally; independent private tally verification pending."

resultHash (published on chain at close) is:
    keccak256(electionId(32) || totalBallots(uint256)
              || for each candidate in chain_index order:
                 candidateId(32) || votes(uint256))
which equals keccak256(abi.encodePacked(...)) for these fixed-width types.
"""

from __future__ import annotations

import uuid

from eth_utils import keccak
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Ballot, Candidate, Election

TALLY_TYPE = "demo_backend"
TALLY_DISCLAIMER = "backend demo tally; independent private tally verification pending."


def compute_tally(db: Session, election: Election) -> dict:
    candidates = db.scalars(
        select(Candidate).where(Candidate.election_id == election.id).order_by(Candidate.chain_index)
    ).all()
    counts: dict[uuid.UUID, int] = dict(
        db.execute(
            select(Ballot.candidate_id, func.count(Ballot.id))
            .where(Ballot.election_id == election.id, Ballot.accepted.is_(True))
            .group_by(Ballot.candidate_id)
        ).all()
    )
    rows = [
        {"candidate_id": str(c.id), "name": c.name, "chain_index": c.chain_index, "votes": counts.get(c.id, 0)}
        for c in candidates
    ]
    return {"total_ballots": sum(r["votes"] for r in rows), "counts": rows}


def compute_result_hash(db: Session, election: Election) -> str:
    """0x-prefixed keccak hash of the canonical tally encoding."""
    from app.services.ids import uuid_to_bytes32

    tally = compute_tally(db, election)
    packed = uuid_to_bytes32(election.id) + tally["total_ballots"].to_bytes(32, "big")
    for row in tally["counts"]:
        packed += uuid_to_bytes32(uuid.UUID(row["candidate_id"])) + row["votes"].to_bytes(32, "big")
    return "0x" + keccak(packed).hex()
