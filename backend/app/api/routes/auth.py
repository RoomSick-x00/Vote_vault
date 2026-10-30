from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.auth.tokens import AuthUser
from app.schemas.auth import AuthMeOut

router = APIRouter()


@router.get("/auth/me", response_model=AuthMeOut)
def whoami(user: AuthUser = Depends(get_current_user)) -> AuthMeOut:
    return AuthMeOut(user_id=str(user.id), email=user.email)
