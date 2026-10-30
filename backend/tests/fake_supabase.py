"""In-memory stand-in for the Supabase Auth proxy used in tests and demos.

Raises the same SupabaseAuthError shapes the real client raises (so route
behavior is identical) and mints HS256 access tokens the app's TokenVerifier
accepts (signed with the app's configured JWT secret).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt as pyjwt

from app.auth.supabase_auth import SupabaseAuthError


class FakeSupabaseAuth:
    def __init__(self, jwt_secret: str) -> None:
        self._secret = jwt_secret
        self.users: dict[str, dict] = {}  # keyed by lowercased email

    def sign_up(self, email: str, password: str, full_name: str) -> dict:
        email = email.lower()
        if email in self.users:
            raise SupabaseAuthError(409, "EMAIL_ALREADY_REGISTERED", "This email is already registered.")
        user_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"fake-auth:{email}"))
        self.users[email] = {
            "id": user_id,
            "email": email,
            "password": password,
            "full_name": full_name,
        }
        return self._session(email)

    def sign_in_with_password(self, email: str, password: str) -> dict:
        email = email.lower()
        user = self.users.get(email)
        if user is None or user["password"] != password:
            raise SupabaseAuthError(401, "UNAUTHENTICATED", "Invalid email or password.")
        return self._session(email)

    # --- internals ---------------------------------------------------------
    def _session(self, email: str) -> dict:
        user = self.users[email]
        now = datetime.now(timezone.utc)
        token = pyjwt.encode(
            {
                "sub": user["id"],
                "email": user["email"],
                "role": "authenticated",
                "user_metadata": {"full_name": user["full_name"]},
                "iat": now,
                "exp": now + timedelta(hours=1),
            },
            self._secret,
            algorithm="HS256",
        )
        return {
            "access_token": token,
            "refresh_token": "fake-refresh-token",
            "token_type": "bearer",
            "expires_in": 3600,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "user_metadata": {"full_name": user["full_name"]},
            },
        }
