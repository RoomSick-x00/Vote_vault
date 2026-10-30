"""Authentication, roles, and the full election lifecycle."""

from __future__ import annotations

import uuid

from fake_chain import FakeChainPublisher
from helpers import (
    ORGANIZER,
    ORGANIZER2,
    OUTSIDER,
    TEST_JWT_SECRET,
    VOTER1,
    add_candidates,
    add_voters,
    auth,
    build_open_election,
    build_ready_election,
    close_election,
    create_election,
    create_organization,
    open_election,
    process_publications,
)


# --- authentication ---------------------------------------------------------


def test_missing_token_is_rejected_with_error_shape(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "UNAUTHENTICATED"


def test_garbage_token_is_rejected(client):
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_wrong_secret_token_is_rejected(client):
    import jwt as pyjwt

    token = pyjwt.encode({"sub": str(ORGANIZER), "exp": 9999999999}, "wrong-secret", algorithm="HS256")
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_expired_token_is_rejected(client):
    import jwt as pyjwt
    from datetime import datetime, timedelta, timezone

    token = pyjwt.encode(
        {"sub": str(ORGANIZER), "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_auth_me_returns_token_identity(client):
    resp = client.get("/api/v1/auth/me", headers=auth(ORGANIZER, "organizer@example.com"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == str(ORGANIZER)
    assert body["email"] == "organizer@example.com"


# --- organizer roles ---------------------------------------------------------


def test_voter_cannot_create_election(client):
    org = create_organization(client, ORGANIZER)
    resp = client.post(
        "/api/v1/elections",
        json={"organization_id": org["organization_id"], "title": "Nope"},
        headers=auth(VOTER1),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_foreign_organizer_cannot_manage_election(client):
    setup = build_ready_election(client)
    election_id = setup["election_id"]
    # ORGANIZER2 has their own org but no membership in the election's org
    create_organization(client, ORGANIZER2, name="Other Club")
    for path, method in [
        (f"/api/v1/elections/{election_id}/open", "post"),
        (f"/api/v1/elections/{election_id}/close", "post"),
        (f"/api/v1/elections/{election_id}/candidates", "post"),
        (f"/api/v1/elections/{election_id}/eligible-test-voters", "get"),
        (f"/api/v1/elections/{election_id}/publications", "get"),
        (f"/api/v1/elections/{election_id}/results", "get"),
    ]:
        resp = getattr(client, method)(path, headers=auth(ORGANIZER2))
        assert resp.status_code == 403, (path, resp.text)
        assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_draft_election_hidden_from_non_organizers(client):
    setup = build_ready_election(client)
    resp = client.get(f"/api/v1/elections/{setup['election_id']}", headers=auth(VOTER1))
    assert resp.status_code == 403
    # organizer sees it
    resp = client.get(f"/api/v1/elections/{setup['election_id']}", headers=auth(ORGANIZER))
    assert resp.status_code == 200
    assert resp.json()["status"] == "draft"


def test_eligible_roster_is_organizer_only(client):
    setup = build_open_election(client)
    resp = client.get(
        f"/api/v1/elections/{setup['election_id']}/eligible-test-voters", headers=auth(VOTER1)
    )
    assert resp.status_code == 403


# --- lifecycle ---------------------------------------------------------------


def test_full_lifecycle_creates_publication_jobs(client, app):
    setup = build_ready_election(client)
    election_id = setup["election_id"]

    # cannot open without candidates/voters is covered below; here we have both
    opened = open_election(client, election_id)
    assert opened["status"] == "open"
    assert opened["opened_at"].endswith("Z")

    closed = close_election(client, election_id)
    assert closed["status"] == "closed"
    assert closed["closed_at"].endswith("Z")

    # register/open/close/publish_result jobs exist; register + open + close + result = 4
    jobs_resp = client.get(
        f"/api/v1/elections/{election_id}/publications", headers=auth(ORGANIZER)
    )
    jobs = jobs_resp.json()
    assert jobs["summary"] == {"pending": 4, "confirmed": 0, "failed": 0}
    assert [j["job_type"] for j in jobs["publications"]] == [
        "register_election",
        "open_election",
        "close_election",
        "publish_result",
    ]


def test_open_requires_candidates_and_voters(client):
    org = create_organization(client, ORGANIZER)
    election = create_election(client, org["organization_id"])
    election_id = election["election_id"]

    resp = client.post(f"/api/v1/elections/{election_id}/open", json={}, headers=auth(ORGANIZER))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ELECTION_HAS_NO_CANDIDATES"

    add_candidates(client, election_id, ["Only Candidate"])
    resp = client.post(f"/api/v1/elections/{election_id}/open", json={}, headers=auth(ORGANIZER))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ELECTION_HAS_NO_VOTERS"

    add_voters(client, election_id, [VOTER1])
    resp = client.post(f"/api/v1/elections/{election_id}/open", json={}, headers=auth(ORGANIZER))
    assert resp.status_code == 200


def test_double_open_and_close_idempotency(client):
    setup = build_ready_election(client)
    election_id = setup["election_id"]
    open_election(client, election_id)
    resp = client.post(f"/api/v1/elections/{election_id}/open", json={}, headers=auth(ORGANIZER))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ELECTION_NOT_DRAFT"

    first = close_election(client, election_id)
    second = client.post(
        f"/api/v1/elections/{election_id}/close", json={}, headers=auth(ORGANIZER)
    )
    assert second.status_code == 200
    assert second.json()["closed_at"] == first["closed_at"]


def test_close_draft_election_rejected(client):
    setup = build_ready_election(client)
    resp = client.post(
        f"/api/v1/elections/{setup['election_id']}/close", json={}, headers=auth(ORGANIZER)
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ELECTION_NOT_OPEN"


def test_candidates_only_in_draft_and_chain_index_stable(client):
    setup = build_ready_election(client)
    election_id = setup["election_id"]
    listing = client.get(
        f"/api/v1/elections/{election_id}/candidates", headers=auth(ORGANIZER)
    ).json()
    assert [c["chain_index"] for c in listing["candidates"]] == [0, 1, 2]

    # duplicate names are skipped, new ones appended with stable indexes
    again = add_candidates(client, election_id, ["Candidate B", "Candidate D"])
    assert again["added"] == 1 and again["skipped"] == 1
    indexes = [c["chain_index"] for c in again["candidates"]]
    assert indexes == [0, 1, 2, 3]

    open_election(client, election_id)
    resp = client.post(
        f"/api/v1/elections/{election_id}/candidates",
        json={"candidates": [{"name": "Late"}]},
        headers=auth(ORGANIZER),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ELECTION_NOT_DRAFT"


def test_results_before_close_rejected(client):
    setup = build_open_election(client)
    resp = client.get(
        f"/api/v1/elections/{setup['election_id']}/results", headers=auth(ORGANIZER)
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ELECTION_NOT_CLOSED"


def test_missing_election_404(client):
    missing = str(uuid.uuid4())
    resp = client.get(f"/api/v1/elections/{missing}", headers=auth(ORGANIZER))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_open_election_visible_to_any_authenticated_user(client):
    setup = build_open_election(client)
    resp = client.get(f"/api/v1/elections/{setup['election_id']}", headers=auth(OUTSIDER))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "open"
    assert len(body["candidates"]) == 3
