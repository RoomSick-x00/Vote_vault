"""Supabase Auth proxy client (public REST API only).

The backend relays email/password signup and login to Supabase Auth using the
project's public anon key — Supabase remains the credential authority, no
service_role key is required, and passwords never touch our database. On
success Supabase returns a session whose access_token our TokenVerifier
already accepts (same project JWKS/JWT secret).
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from app.errors import ApiError


class SupabaseAuthError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class SupabaseAuthLike(Protocol):
    def sign_up(self, email: str, password: str, full_name: str) -> dict: ...

    def sign_in_with_password(self, email: str, password: str) -> dict: ...


class SupabaseAuthClient:
    def __init__(self, supabase_url: str, anon_key: str, timeout: float = 10.0) -> None:
        self._base_url = supabase_url.rstrip("/")
        self._anon_key = anon_key
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"apikey": self._anon_key, "Content-Type": "application/json"}

    def sign_up(self, email: str, password: str, full_name: str) -> dict:
        return self._request(
            "POST",
            "/auth/v1/signup",
            json={"email": email, "password": password, "data": {"full_name": full_name}},
            invalid_credentials_message="Signup rejected by the auth provider.",
        )

    def sign_in_with_password(self, email: str, password: str) -> dict:
        return self._request(
            "POST",
            "/auth/v1/token?grant_type=password",
            json={"email": email, "password": password},
            invalid_credentials_message="Invalid email or password.",
        )

    def _request(self, method: str, path: str, *, json: dict, invalid_credentials_message: str) -> dict:
        try:
            response = httpx.request(
                method,
                self._base_url + path,
                json=json,
                headers=self._headers(),
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise SupabaseAuthError(
                502, "AUTH_UPSTREAM_UNAVAILABLE", f"Auth provider unreachable: {exc}"
            ) from exc

        body: Any = None
        try:
            body = response.json()
        except ValueError:
            pass

        if response.is_success:
            if not isinstance(body, dict) or not body.get("access_token"):
                # Supabase returns 200 without a session when email confirmation is on.
                raise SupabaseAuthError(
                    403,
                    "EMAIL_CONFIRMATION_REQUIRED",
                    "Email confirmation is enabled on the auth project; confirm the "
                    "address before logging in (or disable it for the demo).",
                )
            return body

        message = ""
        if isinstance(body, dict):
            message = str(body.get("msg") or body.get("message") or body.get("error_description") or "")
        lowered = message.lower()
        if "already" in lowered and "regist" in lowered:
            raise SupabaseAuthError(409, "EMAIL_ALREADY_REGISTERED", "This email is already registered.")
        if response.status_code in (400, 401, 403) and ("invalid" in lowered or "credential" in lowered):
            raise SupabaseAuthError(401, "UNAUTHENTICATED", invalid_credentials_message)
        raise SupabaseAuthError(
            502, "AUTH_UPSTREAM_ERROR", message or f"Auth provider error (HTTP {response.status_code})."
        )


def auth_error_to_api(exc: SupabaseAuthError) -> ApiError:
    return ApiError(exc.status_code, exc.code, exc.message)
