"""initial source registry

Revision ID: 001_initial
Revises:
Create Date: 2026-09-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'sources',
        sa.Column('source_id', sa.String(length=64), nullable=False),
        sa.Column('source_name', sa.String(length=255), nullable=False),
        sa.Column('organization', sa.String(length=255), nullable=False),
        sa.Column('url', sa.String(length=512), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('access_method', sa.String(length=50), nullable=False),
        sa.Column('freshness_class', sa.String(length=50), nullable=False),
        sa.Column('last_verified_at', sa.DateTime(), nullable=True),
        sa.Column('last_fetched_at', sa.DateTime(), nullable=True),
        sa.Column('coverage', sa.String(length=255), nullable=True),
        sa.Column('historical_depth', sa.String(length=255), nullable=True),
        sa.Column('reliability_notes', sa.Text(), nullable=True),
        sa.Column('legal_access_notes', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=True),
        sa.PrimaryKeyConstraint('source_id')
    )
    op.create_index(op.f('ix_sources_source_id'), 'sources', ['source_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_sources_source_id'), table_name='sources')
    op.drop_table('sources')
