"""Publication jobs: confirmation, honest failure states, retries, operator requeue."""

from __future__ import annotations

from helpers import ORGANIZER, auth, build_open_election, close_election, process_publications, vote


def _voter_token(setup, roll_no="R001") -> str:
    return setup["token_for"](roll_no)


def _submit_ballot(client, setup, roll_no="R001", candidate_index=0) -> dict:
    resp = vote(
        client,
        setup["election_id"],
        setup["candidates"][candidate_index]["candidate_id"],
        _voter_token(setup, roll_no),
    )
    assert resp.status_code == 202, resp.text
    return resp.json()


def _receipt(client, setup, receipt_id, roll_no="R001") -> dict:
    resp = client.get(
        f"/api/v1/elections/{setup['election_id']}/receipts/{receipt_id}",
        headers={"Authorization": f"Bearer {_voter_token(setup, roll_no)}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_full_job_pipeline_confirms(client, app, fake_publisher):
    setup = build_open_election(client)
    ballot = _submit_ballot(client, setup)

    summary = process_publications(app)
    # register_election + open_election + publish_ballot all confirm
    assert summary == {"confirmed": 3, "retry_scheduled": 0, "failed": 0}

    receipt = _receipt(client, setup, ballot["receipt_id"])
    assert receipt["status"] == "confirmed"
    assert receipt["transaction_hash"].startswith("0x")
    assert receipt["block_number"] >= 1
    assert receipt["error"] is None

    pubs = client.get(
        f"/api/v1/elections/{setup['election_id']}/publications", headers=auth(ORGANIZER)
    ).json()
    assert pubs["summary"] == {"pending": 0, "confirmed": 3, "failed": 0}

    # the submitted chain payload uses the agreed encodings
    ballot_jobs = [c for c in fake_publisher.submit_calls if c[0] == "publish_ballot"]
    assert len(ballot_jobs) == 1
    payload = ballot_jobs[0][1]
    assert payload["election_id"] == "0x" + "00" * 16 + setup["election_id"].replace("-", "")
    assert payload["ballot_id"] == "0x" + "00" * 16 + ballot["receipt_id"].replace("-", "")
    assert payload["commitment"] == receipt["commitment"]


def test_submit_failure_retries_then_fails_then_operator_retry(client, app, fake_publisher):
    setup = build_open_election(client)
    ballot = _submit_ballot(client, setup)

    # lifecycle jobs (register/open) succeed; the ballot job's RPC fails 3x
    fake_publisher.script_next("ok", times=2)      # register, open
    fake_publisher.script_next("raise", "Hardhat down", times=3)  # ballot attempts 1..3

    assert process_publications(app) == {"confirmed": 2, "retry_scheduled": 1, "failed": 0}
    assert process_publications(app) == {"confirmed": 0, "retry_scheduled": 1, "failed": 0}
    assert process_publications(app) == {"confirmed": 0, "retry_scheduled": 0, "failed": 1}
    # exhausted: nothing more to do
    assert process_publications(app) == {"confirmed": 0, "retry_scheduled": 0, "failed": 0}

    receipt = _receipt(client, setup, ballot["receipt_id"])
    assert receipt["status"] == "failed"
    assert "Hardhat down" in receipt["error"]
    assert receipt["transaction_hash"] is None  # never reached the chain

    # operator retry resets the budget; the chain is back up
    resp = client.post(
        f"/api/v1/elections/{setup['election_id']}/publications/retry", headers=auth(ORGANIZER)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["requeued"] >= 1
    assert body["processed"]["confirmed"] >= 1
    assert _receipt(client, setup, ballot["receipt_id"])["status"] == "confirmed"


def test_reverted_transaction_is_a_failure_and_next_tx_confirms(client, app, fake_publisher):
    setup = build_open_election(client)
    ballot = _submit_ballot(client, setup)

    fake_publisher.script_next("ok", times=2)      # register, open
    fake_publisher.script_next("revert")            # ballot attempt 1: mined, status 0

    assert process_publications(app) == {"confirmed": 2, "retry_scheduled": 1, "failed": 0}
    receipt = _receipt(client, setup, ballot["receipt_id"])
    assert receipt["status"] == "pending"  # honest: reverted, will retry

    assert process_publications(app) == {"confirmed": 1, "retry_scheduled": 0, "failed": 0}
    receipt = _receipt(client, setup, ballot["receipt_id"])
    assert receipt["status"] == "confirmed"
    assert receipt["block_number"] >= 1


def test_lost_receipt_is_retried_not_assumed(client, app, fake_publisher):
    setup = build_open_election(client)
    ballot = _submit_ballot(client, setup)

    fake_publisher.script_next("ok", times=2)   # register, open
    fake_publisher.script_next("timeout")       # ballot attempt 1: tx sent, no receipt

    assert process_publications(app) == {"confirmed": 2, "retry_scheduled": 1, "failed": 0}
    receipt = _receipt(client, setup, ballot["receipt_id"])
    assert receipt["status"] == "pending"
    assert receipt["transaction_hash"].startswith("0x")  # first tx recorded

    assert process_publications(app) == {"confirmed": 1, "retry_scheduled": 0, "failed": 0}
    receipt = _receipt(client, setup, ballot["receipt_id"])
    assert receipt["status"] == "confirmed"


def test_status_one_without_matching_event_is_not_confirmed(client, app, fake_publisher):
    setup = build_open_election(client)
    ballot = _submit_ballot(client, setup)

    fake_publisher.script_next("ok", times=2)
    fake_publisher.script_next("no_event")  # mined, status 1, event absent

    assert process_publications(app) == {"confirmed": 2, "retry_scheduled": 1, "failed": 0}
    receipt = _receipt(client, setup, ballot["receipt_id"])
    assert receipt["status"] == "pending"
    assert "expected event" in receipt["error"]


def test_close_creates_result_jobs_and_they_confirm(client, app, fake_publisher):
    setup = build_open_election(client)
    _submit_ballot(client, setup, "R001", 0)
    close_election(client, setup["election_id"])

    summary = process_publications(app)
    # register, open, ballot, close, result
    assert summary == {"confirmed": 5, "retry_scheduled": 0, "failed": 0}

    pubs = client.get(
        f"/api/v1/elections/{setup['election_id']}/publications", headers=auth(ORGANIZER)
    ).json()
    result_jobs = [p for p in pubs["publications"] if p["job_type"] == "publish_result"]
    assert len(result_jobs) == 1 and result_jobs[0]["status"] == "confirmed"


def test_ballot_and_job_are_atomic(client, app):
    """A submitted ballot always has its publication job — same transaction."""
    from sqlalchemy import select

    from app.models import Ballot, PublicationJob

    setup = build_open_election(client)
    _submit_ballot(client, setup)

    with app.state.sessionmaker() as db:
        ballots = db.scalars(select(Ballot)).all()
        jobs = db.scalars(select(PublicationJob)).all()
        assert len(ballots) == 1
        publish_jobs = [j for j in jobs if j.job_type == "publish_ballot"]
        assert len(publish_jobs) == 1
        assert publish_jobs[0].ballot_id == ballots[0].id
