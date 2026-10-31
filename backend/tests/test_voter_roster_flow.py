"""Voter roster upload, identify/OTP security, and the voter session flow."""

from __future__ import annotations

import uuid

from helpers import (
    ORGANIZER,
    OUTSIDER,
    TEST_JWT_SECRET,
    auth,
    build_open_election,
    build_ready_election,
    close_election,
    open_election,
    roster_csv,
    upload_roster,
)
import jwt as pyjwt


def _identify(client, code, roll_no="R001", extra=None):
    body = {"rollNo": roll_no}
    if extra:
        body.update(extra)
    return client.post(f"/api/v1/vote/{code}/identify", json=body)


def _otp_request(client, identify_token, channel="email", contact=None):
    return client.post(
        "/api/v1/vote/otp/request",
        json={"identifyToken": identify_token, "channel": channel, "contact": contact or "r001@campus.edu"},
    )


def _verify(client, identify_token, otp):
    return client.post("/api/v1/vote/otp/verify", json={"identifyToken": identify_token, "otp": otp})


def test_csv_upload_report_and_roster_listing(client):
    setup = build_ready_election(client)
    report = setup["import_report"]
    assert report == {"imported": 3, "skipped": 0, "errors": [], "columns": ["name", "rollNo", "email", "phone"]}

    listing = client.get(
        f"/api/v1/elections/{setup['election_id']}/voters", headers=auth(ORGANIZER)
    ).json()
    assert listing["voterCount"] == 3
    first = listing["voters"][0]
    assert first["rollNo"] == "R001" and first["hasVoted"] is False
    assert first["addedAt"].endswith("Z")

    # duplicate roll number -> skipped with an error entry
    again = upload_roster(client, setup["election_id"], roster_csv())
    assert again["imported"] == 0 and again["errors"][0]["message"].startswith("duplicate roll number")


def test_csv_rows_missing_required_columns_reported(client):
    setup = build_ready_election(client)
    csv_text = "name,email\nNo Roll, nr@campus.edu\n"  # missing rollNo (identity) and phone ok
    report = upload_roster(client, setup["election_id"], csv_text)
    assert report["imported"] == 0
    assert report["errors"][0]["row"] == 2
    assert "rollNo" in report["errors"][0]["message"]


def test_public_election_preview_and_privacy(client):
    setup = build_open_election(client)
    code = setup["election"]["code"]
    preview = client.get(f"/api/v1/vote/{code}")
    assert preview.status_code == 200
    body = preview.json()
    assert body["code"] == code and body["status"] == "open"
    assert body["voterSchema"]["identityColumns"] == ["rollNo"]
    assert "candidates" not in body  # candidates come with the verified session

    assert client.get("/api/v1/vote/ZZZZZZZZ").status_code == 404

    draft = build_ready_election(client)
    assert client.get(f"/api/v1/vote/{draft['election']['code']}").status_code == 404


def test_identify_errors(client):
    setup = build_open_election(client)
    code = setup["election"]["code"]

    resp = _identify(client, code, roll_no="R999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "VOTER_NOT_FOUND"

    resp = _identify(client, code, extra={"rollNo": ""})  # missing identity value
    assert resp.status_code == 422

    resp = _identify(client, "badcode123")
    assert resp.status_code == 404


def test_otp_security(client):
    setup = build_open_election(client)
    code = setup["election"]["code"]

    # wrong contact (not on the roster for this voter)
    identify = _identify(client, code)
    token = identify.json()["identifyToken"]
    resp = _otp_request(client, token, contact="attacker@evil.edu")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CONTACT_MISMATCH"

    # channel not enabled for this election
    resp = _otp_request(client, token, channel="phone", contact="5550101")
    assert resp.status_code == 422

    # resend too soon
    first = _otp_request(client, token)
    assert first.status_code == 200 and first.json()["devCode"]
    second = _otp_request(client, token)
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "OTP_RESEND_TOO_SOON"

    # wrong code burns an attempt but stays alive; right code then works
    wrong = _verify(client, token, "000000")
    assert wrong.status_code == 401 and wrong.json()["error"]["code"] == "OTP_INVALID"
    ok = _verify(client, token, first.json()["devCode"])
    assert ok.status_code == 200
    session_token = ok.json()["token"]

    # consumed challenge cannot be verified twice
    again = _verify(client, token, first.json()["devCode"])
    assert again.status_code == 404 and again.json()["error"]["code"] == "OTP_NOT_FOUND"

    # forged/foreign tokens are rejected at voter endpoints
    forged = pyjwt.encode(
        {"scope": "voter", "vtr": str(uuid.uuid4()), "elc": setup["election_id"], "exp": 9999999999,
         "jti": "x"},
        TEST_JWT_SECRET, algorithm="HS256",
    )
    resp = client.get("/api/v1/vote/session", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401  # unknown voter id

    supabase = auth(OUTSIDER)["Authorization"].split(" ", 1)[1]
    resp = client.get("/api/v1/vote/session", headers={"Authorization": f"Bearer {supabase}"})
    assert resp.status_code == 401  # Supabase tokens lack the voter scope

    # ...and voter tokens are rejected at organizer endpoints
    resp = client.get(
        f"/api/v1/elections/{setup['election_id']}", headers={"Authorization": f"Bearer {session_token}"}
    )
    assert resp.status_code == 401


def test_voter_session_shows_voted_state_and_receipt(client, app):
    setup = build_open_election(client)
    code = setup["election"]["code"]

    identify = _identify(client, code)
    token = identify.json()["identifyToken"]
    otp = _otp_request(client, token).json()["devCode"]
    session = _verify(client, token, otp).json()
    assert session["session"]["hasVoted"] is False and session["session"]["receiptId"] is None

    vote_resp = client.post(
        "/api/v1/vote/ballot",
        json={"candidateId": setup["candidates"][1]["candidate_id"]},
        headers={"Authorization": f"Bearer {session['token']}"},
    )
    assert vote_resp.status_code == 202, vote_resp.text
    receipt = vote_resp.json()
    assert receipt["receiptId"] and receipt["commitment"].startswith("0x")
    assert receipt["status"] == "pending" and receipt["confirmedAt"] is None

    # identical retry through the flow endpoint returns the same receipt id
    retry = client.post(
        "/api/v1/vote/ballot",
        json={"candidateId": setup["candidates"][1]["candidate_id"]},
        headers={"Authorization": f"Bearer {session['token']}"},
    )
    assert retry.json()["receiptId"] == receipt["receiptId"]

    session_now = client.get(
        "/api/v1/vote/session", headers={"Authorization": f"Bearer {session['token']}"}
    ).json()
    assert session_now["hasVoted"] is True
    assert session_now["receiptId"] == receipt["receiptId"]
    assert [c["name"] for c in session_now["candidates"]] == [
        "Candidate A", "Candidate B", "Candidate C",
    ]

    from helpers import process_publications
    process_publications(app)
    receipt_view = client.get(
        "/api/v1/vote/receipt", headers={"Authorization": f"Bearer {session['token']}"}
    ).json()
    assert receipt_view["status"] == "confirmed" and receipt_view["txHash"]


def test_roster_delete_rules(client):
    setup = build_ready_election(client)
    listing = client.get(
        f"/api/v1/elections/{setup['election_id']}/voters", headers=auth(ORGANIZER)
    ).json()
    voter_id = listing["voters"][2]["id"]

    deleted = client.delete(
        f"/api/v1/elections/{setup['election_id']}/voters/{voter_id}", headers=auth(ORGANIZER)
    )
    assert deleted.status_code == 204

    open_election(client, setup["election_id"], ORGANIZER)
    listing2 = client.get(
        f"/api/v1/elections/{setup['election_id']}/voters", headers=auth(ORGANIZER)
    ).json()
    remaining = listing2["voters"][0]["id"]
    blocked = client.delete(
        f"/api/v1/elections/{setup['election_id']}/voters/{remaining}", headers=auth(ORGANIZER)
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "ELECTION_NOT_DRAFT"
