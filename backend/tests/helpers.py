"""Shared test helpers: synthetic users, token minting, API flow builders."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt as pyjwt

# Synthetic Supabase-Auth-style test users (UUIDv4-shaped, fixed for readability).
ORGANIZER = uuid.UUID("11111111-1111-4111-8111-111111111111")
ORGANIZER2 = uuid.UUID("22222222-2222-4222-8222-222222222222")  # organizer of another org
VOTER1 = uuid.UUID("33333333-3333-4333-8333-333333333333")
VOTER2 = uuid.UUID("44444444-4444-4444-8444-444444444444")
VOTER3 = uuid.UUID("55555555-5555-4555-8555-555555555555")
OUTSIDER = uuid.UUID("66666666-6666-4666-8666-666666666666")  # authenticated, not eligible

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


def add_voters(client, election_id, user_ids, user_id=ORGANIZER) -> dict:
    resp = client.post(
        f"/api/v1/elections/{election_id}/eligible-test-voters",
        json={"user_ids": [str(u) for u in user_ids]},
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


def vote(client, election_id, candidate_id, user_id):
    return client.post(
        f"/api/v1/elections/{election_id}/ballots",
        json={"candidate_id": str(candidate_id)},
        headers=auth(user_id),
    )


def build_ready_election(client, *, voter_ids=(VOTER1, VOTER2, VOTER3), organizer=ORGANIZER):
    """org + election (draft) with 3 candidates and eligible voters added."""
    org = create_organization(client, organizer)
    election = create_election(client, org["organization_id"], organizer)
    candidates = add_candidates(
        client, election["election_id"], ["Candidate A", "Candidate B", "Candidate C"], organizer
    )
    add_voters(client, election["election_id"], voter_ids, organizer)
    return {
        "org": org,
        "election": election,
        "election_id": election["election_id"],
        "candidates": candidates["candidates"],
        "voter_ids": list(voter_ids),
        "organizer": organizer,
    }


def build_open_election(client, **kwargs):
    setup = build_ready_election(client, **kwargs)
    open_election(client, setup["election_id"], setup["organizer"])
    return setup


def process_publications(app) -> dict:
    from app.services import publication_service

    return publication_service.process_due_jobs(
        app.state.sessionmaker, app.state.publisher, app.state.settings
    )
