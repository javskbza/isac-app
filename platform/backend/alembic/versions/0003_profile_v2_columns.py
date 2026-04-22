"""v2 profile columns — total_rows, total_columns, zscore_anomalies

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-22 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('profiles',
        sa.Column('total_rows', sa.Integer(), nullable=True)
    )
    op.add_column('profiles',
        sa.Column('total_columns', sa.Integer(), nullable=True)
    )
    op.add_column('profiles',
        sa.Column('zscore_anomalies', postgresql.JSONB(astext_type=sa.Text()),
                  nullable=True, server_default='[]')
    )


def downgrade() -> None:
    op.drop_column('profiles', 'zscore_anomalies')
    op.drop_column('profiles', 'total_columns')
    op.drop_column('profiles', 'total_rows')
