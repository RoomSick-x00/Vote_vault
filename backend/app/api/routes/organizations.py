from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.auth.tokens import AuthUser
from app.errors import ApiError
from app.models import Organization, OrgMembership
from app.schemas.organizations import (
    OrganizationCreateIn,
    OrganizationListOut,
    OrganizationOut,
)

router = APIRouter()


@router.post("", status_code=201, response_model=OrganizationOut)
def create_organization(
    payload: OrganizationCreateIn,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrganizationOut:
    """Any authenticated user can found an organization and becomes its owner
    (organizer role). This is the organizer bootstrap for milestone 1."""
    org = Organization(name=payload.name, created_by=user.id)
    db.add(org)
    db.flush()
    db.add(OrgMembership(organization_id=org.id, user_id=user.id, role="owner"))
    db.commit()
    db.refresh(org)
    return OrganizationOut.build(
        organization_id=org.id, name=org.name, role="owner", created_at=org.created_at
    )


@router.get("", response_model=OrganizationListOut)
def list_my_organizations(
    user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> OrganizationListOut:
    rows = db.execute(
        select(Organization, OrgMembership)
        .join(OrgMembership, OrgMembership.organization_id == Organization.id)
        .where(OrgMembership.user_id == user.id)
        .order_by(Organization.created_at)
    ).all()
    return OrganizationListOut(
        organizations=[
            OrganizationOut.build(
                organization_id=org.id, name=org.name, role=membership.role, created_at=org.created_at
            )
            for org, membership in rows
        ]
    )
