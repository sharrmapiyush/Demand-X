"""add demand aggregation tables

Revision ID: 005_demand_aggregation
Revises: 004_dvet_supply
Create Date: 2026-09-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005_demand_aggregation'
down_revision = '004_dvet_supply'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # demand_calculation_runs table
    op.create_table(
        'demand_calculation_runs',
        sa.Column('run_id', sa.String(length=64), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('input_data_start_date', sa.Date(), nullable=True),
        sa.Column('input_data_end_date', sa.Date(), nullable=True),
        sa.Column('rule_version', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint('run_id')
    )
    op.create_index(op.f('ix_demand_calculation_runs_started_at'), 'demand_calculation_runs', ['started_at'], unique=False)
    op.create_index(op.f('ix_demand_calculation_runs_status'), 'demand_calculation_runs', ['status'], unique=False)

    # district_occupation_demand table
    op.create_table(
        'district_occupation_demand',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('run_id', sa.String(length=64), nullable=False),
        sa.Column('district', sa.String(length=100), nullable=False),
        sa.Column('occupation_id', sa.String(length=64), nullable=False),
        sa.Column('sector', sa.String(length=100), nullable=True),
        sa.Column('observation_period_start', sa.Date(), nullable=False),
        sa.Column('observation_period_end', sa.Date(), nullable=False),
        sa.Column('job_count', sa.Integer(), nullable=False),
        sa.Column('apprenticeship_count', sa.Integer(), nullable=False),
        sa.Column('demand_score', sa.Float(), nullable=True),
        sa.Column('data_completeness_status', sa.String(length=50), nullable=False),
        sa.Column('source_coverage_summary', sa.JSON(), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=True),
        sa.Column('provenance_state', sa.String(length=50), nullable=False),
        sa.Column('rule_version', sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['demand_calculation_runs.run_id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('district', 'occupation_id', 'observation_period_start', 'observation_period_end', 'run_id', name='uix_occupation_demand_composite')
    )
    op.create_index(op.f('ix_district_occupation_demand_run_id'), 'district_occupation_demand', ['run_id'], unique=False)
    op.create_index(op.f('ix_district_occupation_demand_district'), 'district_occupation_demand', ['district'], unique=False)
    op.create_index(op.f('ix_district_occupation_demand_occupation_id'), 'district_occupation_demand', ['occupation_id'], unique=False)
    op.create_index(op.f('ix_district_occupation_demand_observation_period_start'), 'district_occupation_demand', ['observation_period_start'], unique=False)
    op.create_index(op.f('ix_district_occupation_demand_observation_period_end'), 'district_occupation_demand', ['observation_period_end'], unique=False)
    op.create_index(op.f('ix_district_occupation_demand_data_completeness_status'), 'district_occupation_demand', ['data_completeness_status'], unique=False)

    # district_skill_demand table
    op.create_table(
        'district_skill_demand',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('run_id', sa.String(length=64), nullable=False),
        sa.Column('district', sa.String(length=100), nullable=False),
        sa.Column('skill_id', sa.String(length=64), nullable=False),
        sa.Column('sector', sa.String(length=100), nullable=True),
        sa.Column('observation_period_start', sa.Date(), nullable=False),
        sa.Column('observation_period_end', sa.Date(), nullable=False),
        sa.Column('normalized_count', sa.Float(), nullable=False),
        sa.Column('demand_score', sa.Float(), nullable=True),
        sa.Column('data_completeness_status', sa.String(length=50), nullable=False),
        sa.Column('source_coverage_summary', sa.JSON(), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=True),
        sa.Column('provenance_state', sa.String(length=50), nullable=False),
        sa.Column('rule_version', sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['demand_calculation_runs.run_id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('district', 'skill_id', 'observation_period_start', 'observation_period_end', 'run_id', name='uix_skill_demand_composite')
    )
    op.create_index(op.f('ix_district_skill_demand_run_id'), 'district_skill_demand', ['run_id'], unique=False)
    op.create_index(op.f('ix_district_skill_demand_district'), 'district_skill_demand', ['district'], unique=False)
    op.create_index(op.f('ix_district_skill_demand_skill_id'), 'district_skill_demand', ['skill_id'], unique=False)
    op.create_index(op.f('ix_district_skill_demand_observation_period_start'), 'district_skill_demand', ['observation_period_start'], unique=False)
    op.create_index(op.f('ix_district_skill_demand_observation_period_end'), 'district_skill_demand', ['observation_period_end'], unique=False)
    op.create_index(op.f('ix_district_skill_demand_data_completeness_status'), 'district_skill_demand', ['data_completeness_status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_district_skill_demand_data_completeness_status'), table_name='district_skill_demand')
    op.drop_index(op.f('ix_district_skill_demand_observation_period_end'), table_name='district_skill_demand')
    op.drop_index(op.f('ix_district_skill_demand_observation_period_start'), table_name='district_skill_demand')
    op.drop_index(op.f('ix_district_skill_demand_skill_id'), table_name='district_skill_demand')
    op.drop_index(op.f('ix_district_skill_demand_district'), table_name='district_skill_demand')
    op.drop_index(op.f('ix_district_skill_demand_run_id'), table_name='district_skill_demand')
    op.drop_table('district_skill_demand')

    op.drop_index(op.f('ix_district_occupation_demand_data_completeness_status'), table_name='district_occupation_demand')
    op.drop_index(op.f('ix_district_occupation_demand_observation_period_end'), table_name='district_occupation_demand')
    op.drop_index(op.f('ix_district_occupation_demand_observation_period_start'), table_name='district_occupation_demand')
    op.drop_index(op.f('ix_district_occupation_demand_occupation_id'), table_name='district_occupation_demand')
    op.drop_index(op.f('ix_district_occupation_demand_district'), table_name='district_occupation_demand')
    op.drop_index(op.f('ix_district_occupation_demand_run_id'), table_name='district_occupation_demand')
    op.drop_table('district_occupation_demand')

    op.drop_index(op.f('ix_demand_calculation_runs_status'), table_name='demand_calculation_runs')
    op.drop_index(op.f('ix_demand_calculation_runs_started_at'), table_name='demand_calculation_runs')
    op.drop_table('demand_calculation_runs')
