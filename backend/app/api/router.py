"""API v1 router assembly. Endpoint shapes: docs/api-contract.md."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    auth,
    ballots,
    candidates,
    elections,
    organizations,
    publications,
    results,
    vote,
    voters,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(elections.router, prefix="/elections", tags=["elections"])
api_router.include_router(candidates.router, prefix="/elections", tags=["elections"])
api_router.include_router(voters.router, prefix="/elections", tags=["elections"])
api_router.include_router(ballots.router, prefix="/elections", tags=["ballots"])
api_router.include_router(publications.router, prefix="/elections", tags=["publications"])
api_router.include_router(results.router, prefix="/elections", tags=["results"])
api_router.include_router(vote.router, tags=["voter flow"])
