"""Persist verification outcomes for frozen script versions."""

import sqlalchemy as sa
from alembic import op

revision = "0005_script_verifications"
down_revision = "0004_projects"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("script_verifications"):
        return
    op.create_table(
        "script_verifications",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("script_id", sa.String(32), nullable=False),
        sa.Column("started_at", sa.Float(), nullable=False),
        sa.Column("completed_at", sa.Float(), nullable=False),
        sa.Column("all_ok", sa.Boolean(), nullable=False),
        sa.Column("journeys_checked", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["script_id"], ["script_snapshots.script_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_script_verifications_script_id", "script_verifications", ["script_id"])


def downgrade():
    op.drop_table("script_verifications")
