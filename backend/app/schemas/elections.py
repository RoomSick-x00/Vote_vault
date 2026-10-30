from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.models import Candidate, Election
from app.schemas.common import APIModel, UtcIso, utc_input_validator


class ElectionCreateIn(APIModel):
    organization_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    opens_at: datetime | None = None
    closes_at: datetime | None = None

    _normalize = utc_input_validator


class CandidateOut(APIModel):
    candidate_id: str
    name: str
    chain_index: int

    @classmethod
    def build(cls, candidate: Candidate) -> "CandidateOut":
        return cls(candidate_id=str(candidate.id), name=candidate.name, chain_index=candidate.chain_index)


class ElectionOut(APIModel):
    election_id: str
    organization_id: str
    title: str
    status: str
    candidates: list[CandidateOut]
    created_at: UtcIso
    opens_at: UtcIso | None = None
    closes_at: UtcIso | None = None
    opened_at: UtcIso | None = None
    closed_at: UtcIso | None = None

    @classmethod
    def build(cls, election: Election, candidates: list[Candidate]) -> "ElectionOut":
        return cls(
            election_id=str(election.id),
            organization_id=str(election.organization_id),
            title=election.title,
            status=election.status,
            candidates=[CandidateOut.build(c) for c in candidates],
            created_at=election.created_at,
            opens_at=election.opens_at,
            closes_at=election.closes_at,
            opened_at=election.opened_at,
            closed_at=election.closed_at,
        )


class OpenElectionOut(APIModel):
    election_id: str
    status: str
    opened_at: UtcIso


class CloseElectionOut(APIModel):
    election_id: str
    status: str
    closed_at: UtcIso


class CandidatesAddIn(APIModel):
    candidates: list[dict] = Field(min_length=1)

    @property
    def names(self) -> list[str]:
        return [str(c.get("name", "")).strip() for c in self.candidates]


class CandidatesOut(APIModel):
    election_id: str
    candidates: list[CandidateOut]


class CandidatesAddOut(CandidatesOut):
    added: int = 0
    skipped: int = 0


class EligibleVotersAddIn(APIModel):
    user_ids: list[uuid.UUID] = Field(min_length=1)


class EligibleVoterOut(APIModel):
    user_id: str


class EligibleVotersOut(APIModel):
    election_id: str
    eligible_test_voters: list[EligibleVoterOut]
    added: int = 0
    skipped: int = 0
