"""Voting rules on ballot submission (single-threaded; races in test_concurrency)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from helpers import (
    ORGANIZER,
    ORGANIZER2,
    OUTSIDER,
    VOTER1,
    VOTER2,
    add_candidates,
    add_voters,
    auth,
    build_open_election,
    build_ready_election,
    close_election,
    create_organization,
    open_election,
    vote,
)


def _vote_ok(client, setup, voter, candidate_index=0):
    resp = vote(client, setup["election_id"], setup["candidates"][candidate_index]["candidate_id"], voter)
    assert resp.status_code == 202, resp.text
    return resp.json()


def test_ineligible_voter_rejected(client):
    setup = build_open_election(client)
    resp = vote(client, setup["election_id"], setup["candidates"][0]["candidate_id"], OUTSIDER)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "NOT_ELIGIBLE"


def test_candidate_from_other_election_rejected(client):
    setup = build_open_election(client)
    other = build_ready_election(client, organizer=ORGANIZER2)  # separate election
    foreign_candidate = other["candidates"][1]["candidate_id"]
    resp = vote(client, setup["election_id"], foreign_candidate, VOTER1)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_CANDIDATE"

    resp = vote(client, setup["election_id"], str(uuid.uuid4()), VOTER1)
    assert resp.status_code == 422


def test_vote_on_draft_rejected(client):
    setup = build_ready_election(client)  # draft: candidates+voters but not opened
    resp = vote(client, setup["election_id"], setup["candidates"][0]["candidate_id"], VOTER1)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ELECTION_NOT_OPEN"


def test_vote_after_close_rejected(client):
    setup = build_open_election(client)
    close_election(client, setup["election_id"])
    resp = vote(client, setup["election_id"], setup["candidates"][0]["candidate_id"], VOTER1)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ELECTION_CLOSED"


def _election_with_window(client, *, opens_at=None, closes_at=None):
    org = create_organization(client, ORGANIZER)
    body = {"organization_id": org["organization_id"], "title": "Windowed"}
    if opens_at:
        body["opens_at"] = opens_at
    if closes_at:
        body["closes_at"] = closes_at
    resp = client.post("/api/v1/elections", json=body, headers=auth(ORGANIZER))
    assert resp.status_code == 201, resp.text
    election_id = resp.json()["election_id"]
    add_candidates(client, election_id, ["A", "B"])
    add_voters(client, election_id, [VOTER1])
    open_election(client, election_id)
    return election_id


def test_vote_window_not_yet_open(client):
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    election_id = _election_with_window(client, opens_at=future)
    resp = client.post(f"/api/v1/elections/{election_id}", headers=auth(ORGANIZER))
    candidates = client.get(
        f"/api/v1/elections/{election_id}/candidates", headers=auth(ORGANIZER)
    ).json()["candidates"]
    resp = vote(client, election_id, candidates[0]["candidate_id"], VOTER1)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ELECTION_NOT_OPEN"


def test_vote_window_already_closed(client):
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    election_id = _election_with_window(client, closes_at=past)
    candidates = client.get(
        f"/api/v1/elections/{election_id}/candidates", headers=auth(ORGANIZER)
    ).json()["candidates"]
    resp = vote(client, election_id, candidates[0]["candidate_id"], VOTER1)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ELECTION_CLOSED"


def test_successful_vote_shape_and_receipt_roundtrip(client):
    setup = build_open_election(client)
    accepted = _vote_ok(client, setup, VOTER1)
    assert accepted["status"] == "pending"
    assert accepted["submitted_at"].endswith("Z")
    assert accepted["idempotent_retry"] is False

    resp = client.get(
        f"/api/v1/elections/{setup['election_id']}/receipts/{accepted['receipt_id']}",
        headers=auth(VOTER1),
    )
    assert resp.status_code == 200, resp.text
    receipt = resp.json()
    assert receipt["ballot_accepted"] is True
    assert receipt["status"] == "pending"
    assert receipt["commitment"].startswith("0x") and len(receipt["commitment"]) == 66
    assert receipt["nonce"].startswith("0x") and len(receipt["nonce"]) == 66
    assert receipt["candidate_id"] == setup["candidates"][0]["candidate_id"]
    assert receipt["transaction_hash"] is None  # not yet submitted to the chain


def test_receipt_private_to_submitting_voter(client):
    setup = build_open_election(client)
    accepted = _vote_ok(client, setup, VOTER1)
    receipt_path = f"/api/v1/elections/{setup['election_id']}/receipts/{accepted['receipt_id']}"
    assert client.get(receipt_path, headers=auth(VOTER2)).status_code == 403
    assert client.get(receipt_path, headers=auth(ORGANIZER)).status_code == 403  # even the organizer
    assert client.get(receipt_path, headers=auth(VOTER1)).status_code == 200


def test_identical_retry_returns_existing_receipt(client):
    setup = build_open_election(client)
    first = _vote_ok(client, setup, VOTER1, candidate_index=1)
    second_json = _vote_ok(client, setup, VOTER1, candidate_index=1)
    assert second_json["receipt_id"] == first["receipt_id"]
    assert second_json["idempotent_retry"] is True
    assert second_json["candidate_id"] == first["candidate_id"]


def test_identical_retry_still_works_after_close(client):
    setup = build_open_election(client)
    first = _vote_ok(client, setup, VOTER1)
    close_election(client, setup["election_id"])
    resp = vote(client, setup["election_id"], first["candidate_id"], VOTER1)
    assert resp.status_code == 202, resp.text
    assert resp.json()["receipt_id"] == first["receipt_id"]
    assert resp.json()["idempotent_retry"] is True


def test_different_second_choice_rejected_original_stands(client):
    setup = build_open_election(client)
    first = _vote_ok(client, setup, VOTER1, candidate_index=0)
    resp = vote(client, setup["election_id"], setup["candidates"][2]["candidate_id"], VOTER1)
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["code"] == "DUPLICATE_VOTE"
    assert "different candidate" in body["error"]["message"]

    receipt = client.get(
        f"/api/v1/elections/{setup['election_id']}/receipts/{first['receipt_id']}",
        headers=auth(VOTER1),
    ).json()
    assert receipt["candidate_id"] == first["candidate_id"]  # original stands


def test_multiple_voters_each_get_one_ballot(client):
    setup = build_open_election(client)
    r1 = _vote_ok(client, setup, VOTER1, candidate_index=0)
    r2 = _vote_ok(client, setup, VOTER2, candidate_index=2)
    assert r1["receipt_id"] != r2["receipt_id"]
    assert r1["candidate_id"] != r2["candidate_id"]


def test_ballot_for_missing_election_404(client):
    resp = vote(client, str(uuid.uuid4()), str(uuid.uuid4()), VOTER1)
    assert resp.status_code == 404
