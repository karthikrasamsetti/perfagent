"""Persist source labels for Review Plan."""

import sqlalchemy as sa
from alembic import op

revision = "0006_plan_review_sources"
down_revision = "0005_script_verifications"
branch_labels = None
depends_on = None


def upgrade():
    columns = sa.inspect(op.get_bind()).get_columns("plans")
    if "review_sources_json" not in {column["name"] for column in columns}:
        op.add_column("plans", sa.Column("review_sources_json", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("plans", "review_sources_json")
