"""Expose incomplete closure until accepted ballots and chain close confirm."""
from alembic import op
import sqlalchemy as sa
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("elections") as batch:
        batch.drop_constraint(op.f("ck_elections_status_values"), type_="check")
        batch.create_check_constraint(op.f("ck_elections_status_values"), "status IN ('draft', 'open', 'closing', 'closed')")

def downgrade():
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT COUNT(*) FROM elections WHERE status = 'closing'")):
        raise RuntimeError("Resolve closing elections before downgrade")
    with op.batch_alter_table("elections") as batch:
        batch.drop_constraint(op.f("ck_elections_status_values"), type_="check")
        batch.create_check_constraint(op.f("ck_elections_status_values"), "status IN ('draft', 'open', 'closed')")
