from __future__ import annotations

from app.schemas.common import APIModel


class ResultCountOut(APIModel):
    candidate_id: str
    name: str
    chain_index: int
    votes: int


class ResultsOut(APIModel):
    election_id: str
    status: str
    tally_type: str
    total_ballots: int
    counts: list[ResultCountOut]
    publications: dict[str, int]
    published_result_status: str
    disclaimer: str
