"""add job postings and apprenticeship opportunities tables

Revision ID: 003_observations
Revises: 002_jobs
Create Date: 2026-09-09 02:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003_observations'
down_revision = '002_jobs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # job_postings table
    op.create_table(
        'job_postings',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('source_id', sa.String(length=64), nullable=False),
        sa.Column('source_record_id', sa.String(length=255), nullable=True),
        sa.Column('job_title', sa.String(length=500), nullable=False),
        sa.Column('employer_name', sa.String(length=500), nullable=True),
        sa.Column('location_text', sa.String(length=500), nullable=True),
        sa.Column('district', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('sector', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('posted_date', sa.Date(), nullable=True),
        sa.Column('retrieved_at', sa.DateTime(), nullable=False),
        sa.Column('source_url', sa.String(length=1000), nullable=True),
        sa.Column('record_identity_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='ACTIVE'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.source_id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('record_identity_hash')
    )
    op.create_index(op.f('ix_job_postings_id'), 'job_postings', ['id'], unique=False)
    op.create_index(op.f('ix_job_postings_source_id'), 'job_postings', ['source_id'], unique=False)
    op.create_index(op.f('ix_job_postings_district'), 'job_postings', ['district'], unique=False)
    op.create_index(op.f('ix_job_postings_state'), 'job_postings', ['state'], unique=False)
    op.create_index(op.f('ix_job_postings_sector'), 'job_postings', ['sector'], unique=False)
    op.create_index(op.f('ix_job_postings_status'), 'job_postings', ['status'], unique=False)
    op.create_index(op.f('ix_job_postings_retrieved_at'), 'job_postings', ['retrieved_at'], unique=False)

    # apprenticeship_opportunities table
    op.create_table(
        'apprenticeship_opportunities',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('source_id', sa.String(length=64), nullable=False),
        sa.Column('source_record_id', sa.String(length=255), nullable=True),
        sa.Column('trade_title', sa.String(length=500), nullable=False),
        sa.Column('organization_name', sa.String(length=500), nullable=True),
        sa.Column('location_text', sa.String(length=500), nullable=True),
        sa.Column('district', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('sector', sa.String(length=100), nullable=True),
        sa.Column('seats_available', sa.Integer(), nullable=True),
        sa.Column('application_start_date', sa.Date(), nullable=True),
        sa.Column('application_end_date', sa.Date(), nullable=True),
        sa.Column('posted_date', sa.Date(), nullable=True),
        sa.Column('retrieved_at', sa.DateTime(), nullable=False),
        sa.Column('source_url', sa.String(length=1000), nullable=True),
        sa.Column('record_identity_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='ACTIVE'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.source_id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('record_identity_hash')
    )
    op.create_index(op.f('ix_apprenticeship_opportunities_id'), 'apprenticeship_opportunities', ['id'], unique=False)
    op.create_index(op.f('ix_apprenticeship_opportunities_source_id'), 'apprenticeship_opportunities', ['source_id'], unique=False)
    op.create_index(op.f('ix_apprenticeship_opportunities_district'), 'apprenticeship_opportunities', ['district'], unique=False)
    op.create_index(op.f('ix_apprenticeship_opportunities_state'), 'apprenticeship_opportunities', ['state'], unique=False)
    op.create_index(op.f('ix_apprenticeship_opportunities_sector'), 'apprenticeship_opportunities', ['sector'], unique=False)
    op.create_index(op.f('ix_apprenticeship_opportunities_status'), 'apprenticeship_opportunities', ['status'], unique=False)
    op.create_index(op.f('ix_apprenticeship_opportunities_retrieved_at'), 'apprenticeship_opportunities', ['retrieved_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_apprenticeship_opportunities_retrieved_at'), table_name='apprenticeship_opportunities')
    op.drop_index(op.f('ix_apprenticeship_opportunities_status'), table_name='apprenticeship_opportunities')
    op.drop_index(op.f('ix_apprenticeship_opportunities_sector'), table_name='apprenticeship_opportunities')
    op.drop_index(op.f('ix_apprenticeship_opportunities_state'), table_name='apprenticeship_opportunities')
    op.drop_index(op.f('ix_apprenticeship_opportunities_district'), table_name='apprenticeship_opportunities')
    op.drop_index(op.f('ix_apprenticeship_opportunities_source_id'), table_name='apprenticeship_opportunities')
    op.drop_index(op.f('ix_apprenticeship_opportunities_id'), table_name='apprenticeship_opportunities')
    op.drop_table('apprenticeship_opportunities')

    op.drop_index(op.f('ix_job_postings_retrieved_at'), table_name='job_postings')
    op.drop_index(op.f('ix_job_postings_status'), table_name='job_postings')
    op.drop_index(op.f('ix_job_postings_sector'), table_name='job_postings')
    op.drop_index(op.f('ix_job_postings_state'), table_name='job_postings')
    op.drop_index(op.f('ix_job_postings_district'), table_name='job_postings')
    op.drop_index(op.f('ix_job_postings_source_id'), table_name='job_postings')
    op.drop_index(op.f('ix_job_postings_id'), table_name='job_postings')
    op.drop_table('job_postings')
