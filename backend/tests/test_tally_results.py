"""Demo tally, disclaimer, and published-result status."""

from __future__ import annotations

import uuid

from helpers import (
    ORGANIZER,
    VOTER1,
    VOTER2,
    VOTER3,
    auth,
    build_open_election,
    close_election,
    process_publications,
    vote,
)


def _results(client, setup):
    resp = client.get(f"/api/v1/elections/{setup['election_id']}/results", headers=auth(ORGANIZER))
    assert resp.status_code == 200, resp.text
    return resp.json()


def _cast(client, setup, voter, index):
    resp = vote(client, setup["election_id"], setup["candidates"][index]["candidate_id"], voter)
    assert resp.status_code == 202, resp.text


def test_results_show_demo_tally_with_disclaimer(client, app):
    setup = build_open_election(client)
    _cast(client, setup, VOTER1, 0)
    _cast(client, setup, VOTER2, 0)
    _cast(client, setup, VOTER3, 1)
    close_election(client, setup["election_id"])

    body = _results(client, setup)
    assert body["tally_type"] == "demo_backend"
    assert body["total_ballots"] == 3
    assert [(c["name"], c["votes"]) for c in body["counts"]] == [
        ("Candidate A", 2),
        ("Candidate B", 1),
        ("Candidate C", 0),
    ]
    assert [c["chain_index"] for c in body["counts"]] == [0, 1, 2]
    assert (
        body["disclaimer"] == "backend demo tally; independent private tally verification pending."
    )
    # before any processing: 3 ballots pending, lifecycle jobs pending too
    assert body["publications"]["pending"] == 7
    assert body["published_result_status"] == "pending"


def test_published_result_status_becomes_confirmed(client, app):
    setup = build_open_election(client)
    _cast(client, setup, VOTER1, 2)
    close_election(client, setup["election_id"])
    process_publications(app)

    body = _results(client, setup)
    assert body["publications"] == {"pending": 0, "confirmed": 5, "failed": 0}
    assert body["published_result_status"] == "confirmed"


def test_published_result_status_failed_when_chain_is_down(client, app, fake_publisher):
    setup = build_open_election(client)
    _cast(client, setup, VOTER1, 0)
    close_election(client, setup["election_id"])
    # 5 jobs x max_attempts(3) raises: nothing ever reaches the chain
    fake_publisher.script_next("raise", "chain down", times=15)

    process_publications(app)
    process_publications(app)
    process_publications(app)
    process_publications(app)

    body = _results(client, setup)
    assert body["published_result_status"] == "failed"
    assert body["publications"]["failed"] == 5
    # the tally is still shown, honestly labeled
    assert body["total_ballots"] == 1


def test_results_organizer_only(client):
    setup = build_open_election(client)
    close_election(client, setup["election_id"])
    resp = client.get(f"/api/v1/elections/{setup['election_id']}/results", headers=auth(VOTER1))
    assert resp.status_code == 403


def test_result_hash_matches_canonical_encoding(client, app):
    """The publish_result payload equals keccak of the agreed tally encoding."""
    from sqlalchemy import select

    from app.models import PublicationJob
    from app.services.ids import uuid_to_bytes32
    from eth_utils import keccak as k

    setup = build_open_election(client)
    _cast(client, setup, VOTER1, 0)
    _cast(client, setup, VOTER2, 1)
    close_election(client, setup["election_id"])

    with app.state.sessionmaker() as db:
        job = db.scalars(
            select(PublicationJob).where(PublicationJob.job_type == "publish_result")
        ).one()
        stored = job.payload["result_hash"]

    election_uuid = uuid.UUID(setup["election_id"])
    candidates = sorted(setup["candidates"], key=lambda c: c["chain_index"])
    votes = [1, 1, 0]  # VOTER1->A, VOTER2->B
    packed = uuid_to_bytes32(election_uuid) + (2).to_bytes(32, "big")
    for candidate, v in zip(candidates, votes):
        packed += uuid_to_bytes32(uuid.UUID(candidate["candidate_id"])) + v.to_bytes(32, "big")
    assert stored == "0x" + k(packed).hex()
