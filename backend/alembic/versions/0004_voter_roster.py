"""voter roster replaces Supabase-based eligibility; shareable election codes

- elections: + code (unique, backfilled), + description, + voter_schema (JSON),
  + candidates.description
- + voters (uploaded roster; unique (election_id, roll_no))
- + voter_otp_challenges
- ballots.voter_id now references voters.id (FK added; existing synthetic rows
  are dev-only)
- eligible_voters dropped (superseded by the uploaded roster)
"""
from __future__ import annotations

import secrets
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L


def _new_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))


def upgrade() -> None:
    op.add_column("elections", sa.Column("code", sa.String(length=12), nullable=True))
    op.add_column("elections", sa.Column("description", sa.String(length=500), nullable=False, server_default=""))
    op.add_column(
        "elections",
        sa.Column(
            "voter_schema",
            sa.JSON(),
            nullable=False,
            server_default='{"identityColumns": ["rollNo"], "otpChannels": ["email"]}',
        ),
    )
    op.add_column("candidates", sa.Column("description", sa.String(length=500), nullable=False, server_default=""))

    # Backfill unique codes for existing rows, then enforce. Batch mode so
    # SQLite dev databases can ALTER constraints (no-op wrapper on Postgres).
    bind = op.get_bind()
    elections = bind.execute(sa.text("SELECT id FROM elections")).fetchall()
    used: set[str] = set()
    for (election_id,) in elections:
        code = _new_code()
        while code in used:
            code = _new_code()
        used.add(code)
        bind.execute(sa.text("UPDATE elections SET code = :c WHERE id = :i"), {"c": code, "i": election_id})
    with op.batch_alter_table("elections") as batch:
        batch.alter_column("code", existing_type=sa.String(length=12), nullable=False)
        batch.create_unique_constraint("uq_elections_code", ["code"])

    op.create_table(
        "voters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("election_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("roll_no", sa.String(length=64), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["election_id"], ["elections.id"], name=op.f("fk_voters_election_id_elections"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_voters")),
        sa.UniqueConstraint("election_id", "roll_no", name=op.f("uq_voters_election_roll_no")),
    )
    op.create_index(op.f("ix_voters_election_id"), "voters", ["election_id"], unique=False)

    op.create_table(
        "voter_otp_challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("election_id", sa.Uuid(), nullable=False),
        sa.Column("voter_id", sa.Uuid(), nullable=False),
        sa.Column("identify_jti", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=8), nullable=False),
        sa.Column("contact", sa.String(length=254), nullable=False),
        sa.Column("code_hash", sa.String(length=66), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["election_id"], ["elections.id"], name=op.f("fk_voter_otp_challenges_election_id_elections"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["voter_id"], ["voters.id"], name=op.f("fk_voter_otp_challenges_voter_id_voters"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_voter_otp_challenges")),
    )
    op.create_index(
        op.f("ix_voter_otp_challenges_election_id"), "voter_otp_challenges", ["election_id"], unique=False
    )
    op.create_index(op.f("ix_voter_otp_challenges_voter_id"), "voter_otp_challenges", ["voter_id"], unique=False)

    # Existing ballots point at legacy synthetic voter ids; milestone-1 dev data
    # only. Re-point is not possible, so ballots are cleared when adopting the
    # roster model.
    bind.execute(sa.text("DELETE FROM ballots"))
    with op.batch_alter_table("ballots") as batch:
        batch.create_foreign_key(
            "fk_ballots_voter_id_voters", "voters", ["voter_id"], ["id"], ondelete="CASCADE"
        )

    op.drop_index(op.f("ix_eligible_voters_election_id"), table_name="eligible_voters")
    op.drop_table("eligible_voters")


def downgrade() -> None:
    op.create_table(
        "eligible_voters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("election_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["election_id"], ["elections.id"], name=op.f("fk_eligible_voters_election_id_elections"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eligible_voters")),
        sa.UniqueConstraint("election_id", "user_id", name=op.f("uq_eligible_voters_election_user")),
    )
    op.create_index(op.f("ix_eligible_voters_election_id"), "eligible_voters", ["election_id"], unique=False)
    with op.batch_alter_table("ballots") as batch:
        batch.drop_constraint("fk_ballots_voter_id_voters", type_="foreignkey")
    op.drop_table("voter_otp_challenges")
    op.drop_table("voters")
    with op.batch_alter_table("elections") as batch:
        batch.drop_constraint("uq_elections_code", type_="unique")
    op.drop_column("elections", "voter_schema")
    op.drop_column("elections", "description")
    op.drop_column("elections", "code")
    op.drop_column("candidates", "description")
