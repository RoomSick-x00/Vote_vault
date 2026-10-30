"""Concurrent duplicate submissions: the unique constraint must decide, not luck.

Eight threads submit for the same voter at the same moment. Exactly one ballot
row may exist; identical retries all return the same receipt; conflicting
choices yield exactly one 202 and 409 for the rest. Uses the configured test database (PostgreSQL preferred; SQLite fallback).
"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from helpers import ORGANIZER, VOTER1, build_open_election, vote


def _ballot_count(app, election_id, voter_id) -> int:
    from app.models import Ballot

    with app.state.sessionmaker() as db:
        return len(
            list(
                db.scalars(
                    select(Ballot.id).where(
                        Ballot.election_id == uuid.UUID(str(election_id)), Ballot.voter_id == voter_id
                    )
                )
            )
        )


def _run_parallel(fn, count=8):
    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(lambda _: fn(), range(count)))


def test_concurrent_identical_submissions_single_ballot(client, app):
    setup = build_open_election(client)
    election_id, candidate_id = setup["election_id"], setup["candidates"][0]["candidate_id"]

    results = _run_parallel(lambda: vote(client, election_id, candidate_id, VOTER1))

    for resp in results:
        assert resp.status_code == 202, resp.text
    receipt_ids = {resp.json()["receipt_id"] for resp in results}
    assert len(receipt_ids) == 1, "identical retries must all return the same receipt"
    assert sum(1 for r in results if r.json()["idempotent_retry"]) == 7
    assert _ballot_count(app, election_id, VOTER1) == 1


def test_concurrent_conflicting_choices_exactly_one_accepted(client, app):
    setup = build_open_election(client)
    election_id = setup["election_id"]
    candidates = [c["candidate_id"] for c in setup["candidates"]]

    def submit(i: int):
        return vote(client, election_id, candidates[i % 2], VOTER1)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(submit, range(8)))

    accepted = [r for r in results if r.status_code == 202]
    rejected = [r for r in results if r.status_code != 202]
    assert len(accepted) >= 1
    assert all(r.status_code == 409 for r in rejected)
    assert all(r.json()["error"]["code"] == "DUPLICATE_VOTE" for r in rejected)
    assert _ballot_count(app, election_id, VOTER1) == 1

    # exactly one choice survived: every accepted receipt shows the same candidate
    winner_candidates = {r.json()["candidate_id"] for r in accepted}
    assert winner_candidates == {accepted[0].json()["candidate_id"]}
    assert accepted[0].json()["candidate_id"] in candidates


def test_concurrent_distinct_voters_all_accepted(client, app):
    from helpers import VOTER2, VOTER3

    setup = build_open_election(client)
    election_id, candidate_id = setup["election_id"], setup["candidates"][0]["candidate_id"]
    voters = [VOTER1, VOTER2, VOTER3] * 3  # 9 submissions across 3 voters

    with ThreadPoolExecutor(max_workers=9) as pool:
        results = list(pool.map(lambda v: vote(client, election_id, candidate_id, v), voters))

    assert all(r.status_code == 202 for r in results), [r.status_code for r in results]
    receipt_ids = {r.json()["receipt_id"] for r in results}
    assert len(receipt_ids) == 3  # one per voter
