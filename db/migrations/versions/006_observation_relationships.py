"""add observation relationships and geographic evidence

Revision ID: 006_observation_relationships
Revises: 005_demand_aggregation
Create Date: 2026-09-10 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '006_observation_relationships'
down_revision = '005_demand_aggregation'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to job_postings
    op.add_column('job_postings', sa.Column('source_skills', sa.Text(), nullable=True))
    op.add_column('job_postings', sa.Column('seats', sa.Integer(), nullable=True))
    op.add_column('job_postings', sa.Column('source_type', sa.String(length=50), nullable=True))
    op.add_column('job_postings', sa.Column('freshness_class', sa.String(length=50), nullable=True))
    op.add_column('job_postings', sa.Column('geographic_evidence', sa.JSON(), nullable=True))

    # Create indexes for new columns
    op.create_index(op.f('ix_job_postings_source_type'), 'job_postings', ['source_type'], unique=False)
    op.create_index(op.f('ix_job_postings_freshness_class'), 'job_postings', ['freshness_class'], unique=False)

    # Create observation_relationships table
    op.create_table(
        'observation_relationships',
        sa.Column('relationship_id', sa.String(length=64), nullable=False),
        sa.Column('relationship_type', sa.String(length=50), nullable=False),
        sa.Column('group_id', sa.String(length=64), nullable=False),
        sa.Column('member_record_id', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['member_record_id'], ['job_postings.id'], ),
        sa.PrimaryKeyConstraint('relationship_id')
    )
    op.create_index(op.f('ix_observation_relationships_group_id'), 'observation_relationships', ['group_id'], unique=False)
    op.create_index(op.f('ix_observation_relationships_relationship_type'), 'observation_relationships', ['relationship_type'], unique=False)
    op.create_index(op.f('ix_observation_relationships_member_record_id'), 'observation_relationships', ['member_record_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_observation_relationships_member_record_id'), table_name='observation_relationships')
    op.drop_index(op.f('ix_observation_relationships_relationship_type'), table_name='observation_relationships')
    op.drop_index(op.f('ix_observation_relationships_group_id'), table_name='observation_relationships')
    op.drop_table('observation_relationships')

    op.drop_index(op.f('ix_job_postings_freshness_class'), table_name='job_postings')
    op.drop_index(op.f('ix_job_postings_source_type'), table_name='job_postings')

    op.drop_column('job_postings', 'geographic_evidence')
    op.drop_column('job_postings', 'freshness_class')
    op.drop_column('job_postings', 'source_type')
    op.drop_column('job_postings', 'seats')
    op.drop_column('job_postings', 'source_skills')
