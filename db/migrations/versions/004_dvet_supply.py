"""add DVET supply tables

Revision ID: 004_dvet_supply
Revises: 003_observations
Create Date: 2026-09-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_dvet_supply'
down_revision = '003_observations'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # dvet_institutes table
    op.create_table(
        'dvet_institutes',
        sa.Column('institute_id', sa.String(length=64), nullable=False),
        sa.Column('institute_code', sa.String(length=64), nullable=True),
        sa.Column('ncvt_mis_code', sa.String(length=64), nullable=True),
        sa.Column('institute_name', sa.String(length=255), nullable=False),
        sa.Column('institute_category', sa.String(length=100), nullable=True),
        sa.Column('district', sa.String(length=100), nullable=False),
        sa.Column('state', sa.String(length=100), nullable=False),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('establishment_year', sa.String(length=50), nullable=True),
        sa.Column('establishment_gr', sa.String(length=255), nullable=True),
        sa.Column('hostel_capacity', sa.String(length=100), nullable=True),
        sa.Column('source_id', sa.String(length=64), nullable=False),
        sa.Column('raw_json', sa.JSON(), nullable=True),
        sa.Column('record_identity_hash', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['source_id'], ['sources.source_id'], ),
        sa.PrimaryKeyConstraint('institute_id'),
        sa.UniqueConstraint('record_identity_hash')
    )
    op.create_index(op.f('ix_dvet_institutes_institute_id'), 'dvet_institutes', ['institute_id'], unique=False)
    op.create_index(op.f('ix_dvet_institutes_institute_code'), 'dvet_institutes', ['institute_code'], unique=False)
    op.create_index(op.f('ix_dvet_institutes_ncvt_mis_code'), 'dvet_institutes', ['ncvt_mis_code'], unique=False)
    op.create_index(op.f('ix_dvet_institutes_source_id'), 'dvet_institutes', ['source_id'], unique=False)
    op.create_index(op.f('ix_dvet_institutes_record_identity_hash'), 'dvet_institutes', ['record_identity_hash'], unique=False)

    # dvet_trades table
    op.create_table(
        'dvet_trades',
        sa.Column('trade_id', sa.String(length=64), nullable=False),
        sa.Column('institute_code', sa.String(length=64), nullable=False),
        sa.Column('institute_name', sa.String(length=255), nullable=True),
        sa.Column('trade_name', sa.String(length=255), nullable=False),
        sa.Column('unit_category', sa.String(length=100), nullable=True),
        sa.Column('intake', sa.String(length=50), nullable=True),
        sa.Column('district', sa.String(length=100), nullable=False),
        sa.Column('state', sa.String(length=100), nullable=False),
        sa.Column('source_id', sa.String(length=64), nullable=False),
        sa.Column('institute_id', sa.String(length=64), nullable=True),
        sa.Column('raw_json', sa.JSON(), nullable=True),
        sa.Column('trade_identity_hash', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['source_id'], ['sources.source_id'], ),
        sa.ForeignKeyConstraint(['institute_id'], ['dvet_institutes.institute_id'], ),
        sa.PrimaryKeyConstraint('trade_id'),
        sa.UniqueConstraint('trade_identity_hash')
    )
    op.create_index(op.f('ix_dvet_trades_trade_id'), 'dvet_trades', ['trade_id'], unique=False)
    op.create_index(op.f('ix_dvet_trades_institute_code'), 'dvet_trades', ['institute_code'], unique=False)
    op.create_index(op.f('ix_dvet_trades_source_id'), 'dvet_trades', ['source_id'], unique=False)
    op.create_index(op.f('ix_dvet_trades_institute_id'), 'dvet_trades', ['institute_id'], unique=False)
    op.create_index(op.f('ix_dvet_trades_trade_identity_hash'), 'dvet_trades', ['trade_identity_hash'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_dvet_trades_trade_identity_hash'), table_name='dvet_trades')
    op.drop_index(op.f('ix_dvet_trades_institute_id'), table_name='dvet_trades')
    op.drop_index(op.f('ix_dvet_trades_source_id'), table_name='dvet_trades')
    op.drop_index(op.f('ix_dvet_trades_institute_code'), table_name='dvet_trades')
    op.drop_index(op.f('ix_dvet_trades_trade_id'), table_name='dvet_trades')
    op.drop_table('dvet_trades')

    op.drop_index(op.f('ix_dvet_institutes_record_identity_hash'), table_name='dvet_institutes')
    op.drop_index(op.f('ix_dvet_institutes_source_id'), table_name='dvet_institutes')
    op.drop_index(op.f('ix_dvet_institutes_ncvt_mis_code'), table_name='dvet_institutes')
    op.drop_index(op.f('ix_dvet_institutes_institute_code'), table_name='dvet_institutes')
    op.drop_index(op.f('ix_dvet_institutes_institute_id'), table_name='dvet_institutes')
    op.drop_table('dvet_institutes')
