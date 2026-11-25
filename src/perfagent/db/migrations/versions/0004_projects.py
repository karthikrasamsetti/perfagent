"""Project organization and reusable workload profiles; retain existing tests."""
from datetime import datetime, timezone
import json

from alembic import op
import sqlalchemy as sa

revision = "0004_projects"
down_revision = "0003_script_snapshots"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    tables = sa.inspect(connection).get_table_names()
    if "projects" not in tables:
        op.create_table("projects", sa.Column("id", sa.String(32), primary_key=True),
                        sa.Column("created_at", sa.DateTime(), nullable=False),
                        sa.Column("name", sa.String(120), nullable=False),
                        sa.Column("description", sa.Text(), nullable=False),
                        sa.Column("settings_json", sa.Text(), nullable=False))
    if "test_workloads" not in tables:
        op.create_table("test_workloads", sa.Column("id", sa.String(32), primary_key=True),
                        sa.Column("plan_id", sa.String(32), nullable=False),
                        sa.Column("name", sa.String(120), nullable=False),
                        sa.Column("profile_json", sa.Text(), nullable=False),
                        sa.Column("thresholds_json", sa.Text(), nullable=False))
        op.create_index("ix_test_workloads_plan_id", "test_workloads", ["plan_id"])
    if "project_id" not in {c["name"] for c in sa.inspect(connection).get_columns("plans")}:
        op.add_column("plans", sa.Column("project_id", sa.String(32), nullable=True))
        op.create_index("ix_plans_project_id", "plans", ["project_id"])
    if "source_key" not in {c["name"] for c in sa.inspect(connection).get_columns("plans")}:
        op.add_column("plans", sa.Column("source_key", sa.String(64), nullable=True))
        op.create_index("ix_plans_source_key", "plans", ["source_key"])
    chat_columns = {c["name"] for c in sa.inspect(connection).get_columns("chat_sessions")}
    if "project_id" not in chat_columns:
        op.add_column("chat_sessions", sa.Column("project_id", sa.String(32), nullable=True))
        op.create_index("ix_chat_sessions_project_id", "chat_sessions", ["project_id"])
    if "test_name" not in chat_columns:
        op.add_column("chat_sessions", sa.Column("test_name", sa.String(120), nullable=True))
    if (connection.execute(sa.text("SELECT count(*) FROM plans WHERE project_id IS NULL")).scalar()
            or connection.execute(sa.text("SELECT count(*) FROM chat_sessions WHERE project_id IS NULL")).scalar()):
        if not connection.execute(sa.text("SELECT id FROM projects WHERE id='legacy'")).first():
            connection.execute(sa.text("INSERT INTO projects (id,created_at,name,description,settings_json) "
                "VALUES (:id,:created,:name,:description,:settings)"), {
                    "id": "legacy", "created": datetime.now(timezone.utc),
                    "name": "Imported workspace", "description": "Tests created before project organization",
                    "settings": json.dumps({"framework_name": "perfagent-tests", "branch": "main"})})
        connection.execute(sa.text("UPDATE plans SET project_id='legacy' WHERE project_id IS NULL"))
        connection.execute(sa.text("UPDATE chat_sessions SET project_id='legacy' WHERE project_id IS NULL"))


def downgrade():
    with op.batch_alter_table("chat_sessions") as batch:
        batch.drop_index("ix_chat_sessions_project_id")
        batch.drop_column("project_id")
        batch.drop_column("test_name")
    with op.batch_alter_table("plans") as batch:
        batch.drop_index("ix_plans_project_id")
        batch.drop_column("project_id")
        batch.drop_index("ix_plans_source_key")
        batch.drop_column("source_key")
    op.drop_table("test_workloads")
    op.drop_table("projects")
