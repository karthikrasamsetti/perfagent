"""add run_records

Revision ID: 3a521ba73e47
Revises: 0001
Create Date: 2026-11-18 11:11:26.936910
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '3a521ba73e47'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # If the table already exists (a database created the old way with
    # Base.metadata.create_all, or a prior full run of this migration),
    # there is nothing to do.
    if 'run_records' in sa.inspect(bind).get_table_names():
        return

    # Postgres only: a previous half-failed run can leave the ENUM type behind
    # without the table, after which creating the table fails on
    # "type runstatus already exists". Drop any orphaned type first so this
    # migration is always safe to re-run.
    if bind.dialect.name == 'postgresql':
        bind.exec_driver_sql('DROP TYPE IF EXISTS runstatus')

    op.create_table('run_records',
    sa.Column('run_id', sa.String(), nullable=False),
    sa.Column('scenario', sa.String(), nullable=False),
    sa.Column('environment', sa.String(), nullable=False),
    sa.Column('target_url', sa.String(), nullable=False),
    sa.Column('load_tool', sa.String(), nullable=False),
    sa.Column('status', sa.Enum('RUNNING', 'PASSED', 'FAILED', 'INCONCLUSIVE', name='runstatus'), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('total_requests', sa.Integer(), nullable=True),
    sa.Column('error_rate', sa.Float(), nullable=True),
    sa.Column('p50_ms', sa.Float(), nullable=True),
    sa.Column('p90_ms', sa.Float(), nullable=True),
    sa.Column('p95_ms', sa.Float(), nullable=True),
    sa.Column('p99_ms', sa.Float(), nullable=True),
    sa.Column('rps', sa.Float(), nullable=True),
    sa.Column('max_vus', sa.Integer(), nullable=True),
    sa.Column('verdict', sa.String(), nullable=True),
    sa.Column('thresholds', sa.JSON(), nullable=True),
    sa.Column('coverage', sa.JSON(), nullable=True),
    sa.Column('ai_narrative', sa.Text(), nullable=True),
    sa.Column('requested_by', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('run_id')
    )
    op.create_index(op.f('ix_run_records_environment'), 'run_records', ['environment'], unique=False)
    op.create_index(op.f('ix_run_records_scenario'), 'run_records', ['scenario'], unique=False)
    op.create_index(op.f('ix_run_records_started_at'), 'run_records', ['started_at'], unique=False)
    op.create_index(op.f('ix_run_records_status'), 'run_records', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_run_records_status'), table_name='run_records')
    op.drop_index(op.f('ix_run_records_started_at'), table_name='run_records')
    op.drop_index(op.f('ix_run_records_scenario'), table_name='run_records')
    op.drop_index(op.f('ix_run_records_environment'), table_name='run_records')
    op.drop_table('run_records')
    # Postgres creates the ENUM type alongside the table but does NOT drop it
    # with the table -- remove it explicitly. checkfirst makes this a no-op on
    # SQLite (which has no enum types) and safe to re-run.
    sa.Enum(name='runstatus').drop(op.get_bind(), checkfirst=True)