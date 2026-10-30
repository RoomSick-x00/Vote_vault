"""initial milestone-1 schema

Revision ID: 0001
Revises:
Create Date: 2026-10-30

Organizations, organizer memberships, elections, candidates, eligible voters,
ballots (one per voter, enforced by unique constraint), publication jobs.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
    )
    op.create_table(
        "org_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_org_memberships_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_org_memberships")),
        sa.CheckConstraint("role IN ('owner', 'organizer')", name=op.f("ck_org_memberships_role_values")),
        sa.UniqueConstraint("organization_id", "user_id", name=op.f("uq_org_memberships_org_user")),
    )
    op.create_index(op.f("ix_org_memberships_user_id"), "org_memberships", ["user_id"], unique=False)

    op.create_table(
        "elections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("opens_at", sa.DateTime(), nullable=True),
        sa.Column("closes_at", sa.DateTime(), nullable=True),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_elections_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_elections")),
        sa.CheckConstraint("status IN ('draft', 'open', 'closed')", name=op.f("ck_elections_status_values")),
    )
    op.create_index(op.f("ix_elections_organization_id"), "elections", ["organization_id"], unique=False)

    op.create_table(
        "candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("election_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("chain_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["election_id"],
            ["elections.id"],
            name=op.f("fk_candidates_election_id_elections"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidates")),
        sa.UniqueConstraint("election_id", "name", name=op.f("uq_candidates_election_name")),
        sa.UniqueConstraint("election_id", "chain_index", name=op.f("uq_candidates_election_chain_index")),
    )
    op.create_index(op.f("ix_candidates_election_id"), "candidates", ["election_id"], unique=False)

    op.create_table(
        "eligible_voters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("election_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["election_id"],
            ["elections.id"],
            name=op.f("fk_eligible_voters_election_id_elections"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eligible_voters")),
        sa.UniqueConstraint("election_id", "user_id", name=op.f("uq_eligible_voters_election_user")),
    )
    op.create_index(op.f("ix_eligible_voters_election_id"), "eligible_voters", ["election_id"], unique=False)

    op.create_table(
        "ballots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("election_id", sa.Uuid(), nullable=False),
        sa.Column("voter_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("nonce", sa.String(length=64), nullable=False),
        sa.Column("commitment", sa.String(length=66), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_ballots_candidate_id_candidates"),
        ),
        sa.ForeignKeyConstraint(
            ["election_id"],
            ["elections.id"],
            name=op.f("fk_ballots_election_id_elections"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ballots")),
        sa.UniqueConstraint("election_id", "voter_id", name=op.f("uq_ballots_election_voter")),
    )
    op.create_index(op.f("ix_ballots_election_id"), "ballots", ["election_id"], unique=False)

    op.create_table(
        "publication_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("election_id", sa.Uuid(), nullable=False),
        sa.Column("ballot_id", sa.Uuid(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("tx_hash", sa.String(length=66), nullable=True),
        sa.Column("block_number", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["ballot_id"],
            ["ballots.id"],
            name=op.f("fk_publication_jobs_ballot_id_ballots"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["election_id"],
            ["elections.id"],
            name=op.f("fk_publication_jobs_election_id_elections"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_publication_jobs")),
        sa.CheckConstraint(
            "job_type IN ('register_election', 'open_election', 'publish_ballot', "
            "'close_election', 'publish_result')",
            name=op.f("ck_publication_jobs_job_type_values"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'failed')",
            name=op.f("ck_publication_jobs_status_values"),
        ),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_publication_jobs_attempts_non_negative")),
    )
    op.create_index(op.f("ix_publication_jobs_election_id"), "publication_jobs", ["election_id"], unique=False)
    op.create_index(op.f("ix_publication_jobs_next_attempt_at"), "publication_jobs", ["next_attempt_at"], unique=False)


def downgrade() -> None:
    op.drop_table("publication_jobs")
    op.drop_table("ballots")
    op.drop_table("eligible_voters")
    op.drop_table("candidates")
    op.drop_table("elections")
    op.drop_table("org_memberships")
    op.drop_table("organizations")
