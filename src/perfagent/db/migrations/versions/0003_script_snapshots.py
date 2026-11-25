"""Immutable inputs for repeatable execution."""
from alembic import op
import sqlalchemy as sa

revision = "0003_script_snapshots"
down_revision = "3a521ba73e47"
branch_labels = None
depends_on = None


def upgrade():
    if "script_snapshots" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "script_snapshots",
        sa.Column("script_id", sa.String(32), primary_key=True),
        sa.Column("load_model_json", sa.Text(), nullable=False),
        sa.Column("data_filename", sa.Text(), nullable=False),
        sa.Column("data_content", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
    )


def downgrade():
    op.drop_table("script_snapshots")
