"""Shared test helpers: synthetic users, tokens, roster upload, voter sessions."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt as pyjwt

# Synthetic Supabase-Auth-style test users (organizers only now).
ORGANIZER = uuid.UUID("11111111-1111-4111-8111-111111111111")
ORGANIZER2 = uuid.UUID("22222222-2222-4222-8222-222222222222")
OUTSIDER = uuid.UUID("66666666-6666-4666-8666-666666666666")

TEST_JWT_SECRET = "votevault-test-jwt-secret-0123456789abcdef"


def make_token(
    user_id: uuid.UUID, email: str = "user@example.com", secret: str = TEST_JWT_SECRET
) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "email": email,
        "role": "authenticated",
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    return pyjwt.encode(claims, secret, algorithm="HS256")


def auth(user_id: uuid.UUID, email: str = "user@example.com") -> dict:
    return {"Authorization": f"Bearer {make_token(user_id, email)}"}


# --- roster -----------------------------------------------------------------

ROSTER = [
    {"name": "Ravi Kumar", "rollNo": "R001", "email": "r001@campus.edu", "phone": "5550101"},
    {"name": "Sara Ahmed", "rollNo": "R002", "email": "r002@campus.edu", "phone": "5550102"},
    {"name": "Tim Park", "rollNo": "R003", "email": "r003@campus.edu", "phone": "5550103"},
]


def roster_csv(rows=None) -> str:
    rows = rows if rows is not None else ROSTER
    header = "name,rollNo,email,phone\n"
    return header + "".join(
        f"{r['name']},{r['rollNo']},{r['email']},{r['phone']}\n" for r in rows
    )


def upload_roster(client, election_id, csv_text: str | None = None, user_id=ORGANIZER) -> dict:
    resp = client.post(
        f"/api/v1/elections/{election_id}/voters/upload",
        files={"file": ("roster.csv", (csv_text or roster_csv()).encode(), "text/csv")},
        headers=auth(user_id),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def voter_session(client, code: str, roll_no: str, email: str | None = None) -> str:
    """identify -> OTP (dev code) -> verify; returns the voter session token."""
    identify = client.post(f"/api/v1/vote/{code}/identify", json={"rollNo": roll_no})
    assert identify.status_code == 200, identify.text
    identify_token = identify.json()["identifyToken"]
    otp = client.post(
        "/api/v1/vote/otp/request",
        json={"identifyToken": identify_token, "channel": "email", "contact": email},
    )
    assert otp.status_code == 200, otp.text
    dev_code = otp.json()["devCode"]
    assert dev_code, "dev OTP delivery must be on in tests"
    verify = client.post("/api/v1/vote/otp/verify", json={"identifyToken": identify_token, "otp": dev_code})
    assert verify.status_code == 200, verify.text
    return verify.json()["token"]


def voter_headers(client, setup: dict, roll_no: str = "R001") -> dict:
    return {"Authorization": f"Bearer {voter_session(client, setup['election']['code'], roll_no)}"}


# --- flow builders ---------------------------------------------------------


def create_organization(client, user_id=ORGANIZER, name="Test Club") -> dict:
    resp = client.post("/api/v1/organizations", json={"name": name}, headers=auth(user_id))
    assert resp.status_code == 201, resp.text
    return resp.json()


def create_election(client, organization_id, user_id=ORGANIZER, title="Club election 2026") -> dict:
    resp = client.post(
        "/api/v1/elections",
        json={"organization_id": str(organization_id), "title": title},
        headers=auth(user_id),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def add_candidates(client, election_id, names, user_id=ORGANIZER) -> dict:
    resp = client.post(
        f"/api/v1/elections/{election_id}/candidates",
        json={"candidates": [{"name": n} for n in names]},
        headers=auth(user_id),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def open_election(client, election_id, user_id=ORGANIZER) -> dict:
    resp = client.post(f"/api/v1/elections/{election_id}/open", json={}, headers=auth(user_id))
    assert resp.status_code == 200, resp.text
    return resp.json()


def close_election(client, election_id, user_id=ORGANIZER) -> dict:
    resp = client.post(f"/api/v1/elections/{election_id}/close", json={}, headers=auth(user_id))
    assert resp.status_code == 200, resp.text
    return resp.json()


def vote(client, election_id, candidate_id, voter_token: str):
    return client.post(
        f"/api/v1/elections/{election_id}/ballots",
        json={"candidate_id": str(candidate_id)},
        headers={"Authorization": f"Bearer {voter_token}"},
    )


def build_ready_election(client, *, organizer=ORGANIZER, roster_rows=None):
    """org + draft election with 3 candidates and an uploaded roster (not open)."""
    org = create_organization(client, organizer)
    election = create_election(client, org["organization_id"], organizer)
    candidates = add_candidates(
        client, election["election_id"], ["Candidate A", "Candidate B", "Candidate C"], organizer
    )
    report = upload_roster(client, election["election_id"], roster_csv(roster_rows), organizer)
    tokens = {
        r["rollNo"]: None for r in (roster_rows or ROSTER)
    }
    setup = {
        "org": org,
        "election": election,
        "election_id": election["election_id"],
        "code": election["code"],
        "candidates": candidates["candidates"],
        "roster": roster_rows or ROSTER,
        "import_report": report,
        "organizer": organizer,
        "_tokens": tokens,
    }
    setup["token_for"] = lambda roll_no="R001": _session_token(client, setup, roll_no)
    return setup


def _session_token(client, setup, roll_no: str) -> str:
    if setup["_tokens"].get(roll_no) is None:
        roster_entry = next(r for r in setup["roster"] if r["rollNo"] == roll_no)
        setup["_tokens"][roll_no] = voter_session(
            client, setup["election"]["code"], roll_no, roster_entry.get("email")
        )
    return setup["_tokens"][roll_no]


def build_open_election(client, **kwargs):
    setup = build_ready_election(client, **kwargs)
    open_election(client, setup["election_id"], setup["organizer"])
    return setup


def process_publications(app) -> dict:
    from app.services import publication_service

    return publication_service.process_due_jobs(
        app.state.sessionmaker, app.state.publisher, app.state.settings
    )
