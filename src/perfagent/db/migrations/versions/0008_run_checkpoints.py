"""Keep temporary checkpoints for active runs."""

import sqlalchemy as sa
from alembic import op

revision = "0008_run_checkpoints"
down_revision = "0007_release_policies"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("run_checkpoints"):
        return
    op.create_table(
        "run_checkpoints",
        sa.Column("run_id", sa.String(32), primary_key=True),
        sa.Column("script_id", sa.String(32), sa.ForeignKey("scripts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("updated_at", sa.Float(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
    )


def downgrade():
    op.drop_table("run_checkpoints")
