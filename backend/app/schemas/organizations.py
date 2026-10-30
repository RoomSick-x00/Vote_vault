from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.common import APIModel, UtcIso


class OrganizationCreateIn(APIModel):
    name: str = Field(min_length=1, max_length=200)


class OrganizationOut(APIModel):
    organization_id: str
    name: str
    role: str
    created_at: UtcIso

    @classmethod
    def build(cls, *, organization_id: uuid.UUID, name: str, role: str, created_at: datetime) -> "OrganizationOut":
        return cls(
            organization_id=str(organization_id),
            name=name,
            role=role,
            created_at=created_at,
        )


class OrganizationListOut(APIModel):
    organizations: list[OrganizationOut]
