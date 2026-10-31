"""Concurrent duplicate submissions: the unique constraint must decide, not luck.

Eight threads per voter submit at the same moment against real PostgreSQL.
Exactly one ballot row may exist per voter; identical retries all return the
same receipt; conflicting choices yield exactly one accepted ballot and 409
for the rest.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import uuid

from sqlalchemy import select

from helpers import build_open_election, vote


def _ballot_count(app, election_id, voter_id) -> int:
    from app.models import Ballot

    with app.state.sessionmaker() as db:
        return len(
            list(
                db.scalars(
                    select(Ballot.id).where(
                        Ballot.election_id == uuid.UUID(election_id), Ballot.voter_id == voter_id
                    )
                )
            )
        )


def _run_parallel(fn, count=8):
    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(lambda _: fn(), range(count)))


def _voter_uuid(app, setup, roll_no: str):
    from app.models import Voter

    with app.state.sessionmaker() as db:
        voter = db.scalars(
            select(Voter).where(Voter.election_id == uuid.UUID(setup["election_id"]), Voter.roll_no == roll_no)
        ).one()
        return voter.id


def test_concurrent_identical_submissions_single_ballot(client, app):
    setup = build_open_election(client)
    election_id = setup["election_id"]
    candidate_id = setup["candidates"][0]["candidate_id"]
    token = setup["token_for"]("R001")
    voter_id = _voter_uuid(app, setup, "R001")

    results = _run_parallel(lambda: vote(client, election_id, candidate_id, token))

    for resp in results:
        assert resp.status_code == 202, resp.text
    receipt_ids = {resp.json()["receipt_id"] for resp in results}
    assert len(receipt_ids) == 1, "identical retries must all return the same receipt"
    assert sum(1 for r in results if r.json()["idempotent_retry"]) == 7
    assert _ballot_count(app, election_id, voter_id) == 1


def test_concurrent_conflicting_choices_exactly_one_accepted(client, app):
    setup = build_open_election(client)
    election_id = setup["election_id"]
    candidates = [c["candidate_id"] for c in setup["candidates"]]
    token = setup["token_for"]("R001")
    voter_id = _voter_uuid(app, setup, "R001")

    def submit(i: int):
        return vote(client, election_id, candidates[i % 2], token)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(submit, range(8)))

    accepted = [r for r in results if r.status_code == 202]
    rejected = [r for r in results if r.status_code != 202]
    assert len(accepted) >= 1
    assert all(r.status_code == 409 for r in rejected)
    assert all(r.json()["error"]["code"] == "DUPLICATE_VOTE" for r in rejected)
    assert _ballot_count(app, election_id, voter_id) == 1

    # exactly one choice survived: every accepted receipt shows the same candidate
    winner_candidates = {r.json()["candidate_id"] for r in accepted}
    assert winner_candidates == {accepted[0].json()["candidate_id"]}
    assert accepted[0].json()["candidate_id"] in candidates


def test_concurrent_distinct_voters_all_accepted(client, app):
    setup = build_open_election(client)
    election_id, candidate_id = setup["election_id"], setup["candidates"][0]["candidate_id"]
    rolls = ["R001", "R002", "R003"]
    tokens = [setup["token_for"](r) for r in rolls]
    voter_ids = [_voter_uuid(app, setup, r) for r in rolls]

    with ThreadPoolExecutor(max_workers=9) as pool:
        results = list(
            pool.map(lambda t: vote(client, election_id, candidate_id, t), [t for t in tokens for _ in range(3)])
        )

    assert all(r.status_code == 202 for r in results), [r.status_code for r in results]
    receipt_ids = {r.json()["receipt_id"] for r in results}
    assert len(receipt_ids) == 3  # one per voter
    for voter_id in voter_ids:
        assert _ballot_count(app, election_id, voter_id) == 1
