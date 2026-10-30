"""Organizer signup/login via the Supabase Auth proxy (fake upstream in tests)."""

from __future__ import annotations

from helpers import ORGANIZER, auth


def _signup(client, email="dana@club.edu", **overrides) -> dict:
    body = {
        "email": email,
        "password": "correct-horse-battery",
        "full_name": "Dana Organizer",
        "organization_name": "Debate Club",
    }
    body.update(overrides)
    return client.post("/api/v1/auth/signup", json=body)


def test_signup_creates_profile_org_membership_and_session(client, fake_supabase):
    resp = _signup(client)
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "dana@club.edu"
    assert body["user"]["full_name"] == "Dana Organizer"
    assert len(body["organizations"]) == 1
    org = body["organizations"][0]
    assert org["name"] == "Debate Club" and org["role"] == "owner"

    # the returned session token is a real Supabase-style JWT our verifier accepts
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["user_id"] == body["user"]["user_id"]
    assert me.json()["full_name"] == "Dana Organizer"
    assert me.json()["organizations"][0]["organization_id"] == org["organization_id"]


def test_signup_duplicate_email_conflict(client, fake_supabase):
    assert _signup(client).status_code == 201
    resp = _signup(client, email="dana@club.edu")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


def test_signup_validation(client, fake_supabase):
    assert _signup(client, password="short").status_code == 422
    assert _signup(client, full_name="").status_code == 422
    assert _signup(client, organization_name="").status_code == 422
    assert _signup(client, email="not-an-email").status_code == 422


def test_signup_requires_configured_upstream(client):
    resp = _signup(client)  # no fake_supabase fixture wired
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "AUTH_UPSTREAM_NOT_CONFIGURED"


def test_login_success_returns_organizations(client, fake_supabase):
    created = _signup(client).json()
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "dana@club.edu", "password": "correct-horse-battery"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["user_id"] == created["user"]["user_id"]
    assert body["user"]["full_name"] == "Dana Organizer"
    assert [o["organization_id"] for o in body["organizations"]] == [
        created["organizations"][0]["organization_id"]
    ]


def test_login_wrong_password_and_unknown_user(client, fake_supabase):
    _signup(client)
    resp = client.post(
        "/api/v1/auth/login", json={"email": "dana@club.edu", "password": "wrong-password"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"

    resp = client.post(
        "/api/v1/auth/login", json={"email": "nobody@club.edu", "password": "whatever-long"}
    )
    assert resp.status_code == 401


def test_signed_up_organizer_runs_the_full_flow(client, fake_supabase):
    """Signup org becomes a working organizer context end-to-end."""
    session = _signup(client).json()
    org_id = session["organizations"][0]["organization_id"]
    token = {"Authorization": f"Bearer {session['access_token']}"}

    resp = client.post(
        "/api/v1/elections",
        json={"organization_id": org_id, "title": "Spring vote"},
        headers=token,
    )
    assert resp.status_code == 201, resp.text

    # a different user must NOT manage this org
    resp = client.post(
        "/api/v1/elections",
        json={"organization_id": org_id, "title": "Hijack"},
        headers=auth(ORGANIZER),
    )
    assert resp.status_code == 403
