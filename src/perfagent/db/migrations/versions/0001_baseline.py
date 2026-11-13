"""Baseline — the schema as it stood when migrations were introduced.

Creates every table on a brand-new database (SQLite or Postgres). It is written to
be safe on a database that pre-dates migrations too: the app used to create its
tables itself on start-up, so on such a database each table already exists and is
simply left as it is, and the database is marked as being at this revision.

Later schema changes are separate revisions on top of this one — never edit this file.

Revision ID: 0001
Revises:
Create Date: 2026-11-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_existing: set[str] = set()


def _create_table(name: str, *items) -> None:
    if name in _existing:
        return                              # already there (pre-migrations database)
    op.create_table(name, *items)


def _create_index(name: str, table: str, columns: list[str], *, unique: bool) -> None:
    if table in _existing:
        return                              # that table kept the indexes it had
    op.create_index(name, table, columns, unique=unique)


def upgrade() -> None:
    _existing.clear()
    _existing.update(sa.inspect(op.get_bind()).get_table_names())

    _create_table('audit',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('action', sa.String(length=40), nullable=False),
        sa.Column('entity', sa.String(length=20), nullable=False),
        sa.Column('entity_id', sa.String(length=32), nullable=False),
        sa.Column('target', sa.String(length=500), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('actor', sa.String(length=80), nullable=False),
        sa.Column('tokens', sa.Integer(), nullable=False),
        sa.Column('cost_usd', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    _create_index('ix_audit_action', 'audit', ['action'], unique=False)
    _create_index('ix_audit_created_at', 'audit', ['created_at'], unique=False)

    _create_table('chat_sessions',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('turns', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    _create_index('ix_chat_sessions_updated_at', 'chat_sessions', ['updated_at'], unique=False)

    _create_table('data_files',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('source_format', sa.String(length=20), nullable=False),
        sa.Column('columns_csv', sa.Text(), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    _create_table('integration_settings',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('plan_id', sa.String(length=32), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('git_json', sa.Text(), nullable=False),
        sa.Column('jenkins_json', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    _create_index('ix_integration_settings_plan_id', 'integration_settings', ['plan_id'],
                  unique=True)

    _create_table('plans',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('target_base_url', sa.String(length=500), nullable=False),
        sa.Column('goal', sa.Text(), nullable=False),
        sa.Column('load_model_json', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    _create_table('run_results',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('plan_id', sa.String(length=32), nullable=False),
        sa.Column('target_base_url', sa.String(length=500), nullable=False),
        sa.Column('verdict', sa.String(length=20), nullable=False),
        sa.Column('requests', sa.Integer(), nullable=False),
        sa.Column('error_rate', sa.Float(), nullable=False),
        sa.Column('rps', sa.Float(), nullable=False),
        sa.Column('p95_ms', sa.Float(), nullable=False),
        sa.Column('p99_ms', sa.Float(), nullable=False),
        sa.Column('avg_ms', sa.Float(), nullable=False),
        sa.Column('goal', sa.Text(), nullable=False),
        sa.Column('report_json', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    _create_index('ix_run_results_plan_id', 'run_results', ['plan_id'], unique=False)

    _create_table('sla_profiles',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('thresholds_json', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    _create_table('traces',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('step', sa.String(length=40), nullable=False),
        sa.Column('model', sa.String(length=80), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False),
        sa.Column('completion_tokens', sa.Integer(), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('redactions', sa.Integer(), nullable=False),
        sa.Column('error', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    _create_index('ix_traces_created_at', 'traces', ['created_at'], unique=False)

    _create_table('scripts',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('plan_id', sa.String(length=32), nullable=False),
        sa.Column('tool', sa.String(length=50), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    raise NotImplementedError("the baseline cannot be downgraded — it is the starting point")
