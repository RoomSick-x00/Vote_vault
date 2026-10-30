"""Supabase Auth access-token verification.

Two verification modes, matching how Supabase projects issue JWTs:
- RS256 against the project JWKS (recommended; configure SUPABASE_URL or
  SUPABASE_JWKS_URL), or
- HS256 with the project's JWT secret (SUPABASE_JWT_SECRET; also the mode used
  for local development and tests, where tokens are minted with the same secret).

`sub` (a UUID) is the canonical user id everywhere in the backend. No voter id
is ever taken from a request body — identity always comes from the token.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import jwt
from jwt import PyJWKClient

from app.errors import ApiError


@dataclass(frozen=True)
class AuthUser:
    id: uuid.UUID
    email: str | None
    role_claim: str | None


class TokenVerifier:
    def __init__(self, jwks_url: str, jwt_secret: str, issuer: str = "") -> None:
        self._jwks_url = jwks_url
        self._jwt_secret = jwt_secret
        self._issuer = issuer or None
        self._jwk_client: PyJWKClient | None = None

    def verify(self, token: str) -> AuthUser:
        try:
            if self._jwks_url:
                if self._jwk_client is None:
                    self._jwk_client = PyJWKClient(self._jwks_url, cache_keys=True)
                key = self._jwk_client.get_signing_key_from_jwt(token).key
                claims = jwt.decode(
                    token,
                    key,
                    algorithms=["RS256", "ES256"],
                    issuer=self._issuer,
                    options={"require": ["exp", "sub"]},
                )
            elif self._jwt_secret:
                claims = jwt.decode(
                    token,
                    self._jwt_secret,
                    algorithms=["HS256"],
                    issuer=self._issuer,
                    options={"require": ["exp", "sub"]},
                )
            else:
                raise ApiError(
                    500,
                    "AUTH_NOT_CONFIGURED",
                    "No JWT verification method configured: set SUPABASE_URL "
                    "(JWKS) or SUPABASE_JWT_SECRET.",
                )
        except ApiError:
            raise
        except jwt.ExpiredSignatureError as exc:
            raise ApiError(401, "UNAUTHENTICATED", "Access token has expired.") from exc
        except jwt.PyJWTError as exc:
            raise ApiError(401, "UNAUTHENTICATED", f"Invalid access token: {exc}") from exc

        sub = claims.get("sub")
        try:
            user_id = uuid.UUID(str(sub))
        except (ValueError, TypeError) as exc:
            raise ApiError(401, "UNAUTHENTICATED", "Token subject is not a valid user id.") from exc

        return AuthUser(id=user_id, email=claims.get("email"), role_claim=claims.get("role"))
