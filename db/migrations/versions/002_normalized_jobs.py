"""normalized jobs and staging tables

Revision ID: 002_jobs
Revises: 001_initial
Create Date: 2026-09-09 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_jobs'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Staging table for raw/unvalidated import
    op.create_table(
        'jobs_staging',
        sa.Column('staging_id', sa.String(length=64), nullable=False),
        sa.Column('source_id', sa.String(length=64), nullable=False),
        sa.Column('source_record_id', sa.String(length=128), nullable=False),
        sa.Column('raw_title', sa.String(length=255), nullable=False),
        sa.Column('raw_employer', sa.String(length=255), nullable=False),
        sa.Column('raw_description', sa.Text(), nullable=True),
        sa.Column('raw_location', sa.String(length=255), nullable=True),
        sa.Column('raw_salary', sa.String(length=255), nullable=True),
        sa.Column('raw_experience', sa.String(length=255), nullable=True),
        sa.Column('raw_education', sa.String(length=255), nullable=True),
        sa.Column('raw_sector', sa.String(length=100), nullable=False),
        sa.Column('raw_district', sa.String(length=100), nullable=False),
        sa.Column('raw_state', sa.String(length=100), nullable=False),
        sa.Column('raw_posted_date', sa.String(length=50), nullable=True),
        sa.Column('raw_json', sa.Text(), nullable=True),
        sa.Column('is_valid', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('validation_errors', sa.Text(), nullable=True),
        sa.Column('processing_status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('job_identity_hash', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('staging_id')
    )
    op.create_index(op.f('ix_jobs_staging_staging_id'), 'jobs_staging', ['staging_id'], unique=False)
    op.create_index(op.f('ix_jobs_staging_source_id'), 'jobs_staging', ['source_id'], unique=False)
    op.create_index(op.f('ix_jobs_staging_job_identity_hash'), 'jobs_staging', ['job_identity_hash'], unique=False)

    # Normalized jobs table
    op.create_table(
        'jobs',
        sa.Column('job_id', sa.String(length=64), nullable=False),
        sa.Column('source_id', sa.String(length=64), nullable=False),
        sa.Column('source_record_id', sa.String(length=128), nullable=False),
        sa.Column('job_title', sa.String(length=255), nullable=False),
        sa.Column('employer_name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=False),
        sa.Column('district', sa.String(length=100), nullable=False),
        sa.Column('location_detail', sa.String(length=255), nullable=True),
        sa.Column('sector', sa.String(length=100), nullable=False),
        sa.Column('experience_years_min', sa.Integer(), nullable=True),
        sa.Column('experience_years_max', sa.Integer(), nullable=True),
        sa.Column('min_education', sa.String(length=255), nullable=True),
        sa.Column('salary_min', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('salary_max', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('salary_currency', sa.String(length=3), nullable=False, server_default='INR'),
        sa.Column('posted_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('job_identity_hash', sa.String(length=64), nullable=False),
        sa.Column('raw_json', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['sources.source_id'], ),
        sa.PrimaryKeyConstraint('job_id')
    )
    op.create_index(op.f('ix_jobs_job_id'), 'jobs', ['job_id'], unique=False)
    op.create_index(op.f('ix_jobs_source_id'), 'jobs', ['source_id'], unique=False)
    op.create_index(op.f('ix_jobs_district'), 'jobs', ['district'], unique=False)
    op.create_index(op.f('ix_jobs_sector'), 'jobs', ['sector'], unique=False)
    op.create_index(op.f('ix_jobs_job_identity_hash'), 'jobs', ['job_identity_hash'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_jobs_job_identity_hash'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_sector'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_district'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_source_id'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_job_id'), table_name='jobs')
    op.drop_table('jobs')

    op.drop_index(op.f('ix_jobs_staging_job_identity_hash'), table_name='jobs_staging')
    op.drop_index(op.f('ix_jobs_staging_source_id'), table_name='jobs_staging')
    op.drop_index(op.f('ix_jobs_staging_staging_id'), table_name='jobs_staging')
    op.drop_table('jobs_staging')
