"""add source provenance columns to sources

Revision ID: 007_source_provenance
Revises: 006_observation_relationships
Create Date: 2026-09-10 18:00:00.000000

Adds canonical source-level provenance columns mirroring the job-posting
provenance added in 006, so the Source Registry can represent a source's
data type, governmental status, and verification posture without needing
source-specific tables. All columns are nullable so existing rows (DVET,
NCS) remain valid.
"""
from alembic import op
import sqlalchemy as sa


revision = '007_source_provenance'
down_revision = '006_observation_relationships'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sources', sa.Column('source_type', sa.String(length=50), nullable=True))
    op.add_column('sources', sa.Column('official_government_source', sa.Boolean(), nullable=True))
    op.add_column('sources', sa.Column('verification_status', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('sources', 'verification_status')
    op.drop_column('sources', 'official_government_source')
    op.drop_column('sources', 'source_type')