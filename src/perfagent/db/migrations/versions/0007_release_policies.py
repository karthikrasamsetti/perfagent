"""Store an approved reference run and release budgets per test environment."""

import sqlalchemy as sa
from alembic import op

revision = "0007_release_policies"
down_revision = "0006_plan_review_sources"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("release_policies"):
        return
    op.create_table(
        "release_policies",
        sa.Column(
            "plan_id",
            sa.String(32),
            sa.ForeignKey("plans.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("environment", sa.Text(), primary_key=True),
        sa.Column(
            "baseline_id",
            sa.String(32),
            sa.ForeignKey("run_results.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("budgets_json", sa.Text(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("release_policies")
