"""initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('role', sa.Enum('admin', 'viewer', name='userrole'), nullable=False, server_default='viewer'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id', name='pk_users'),
        sa.UniqueConstraint('email', name='uq_users_email'),
    )

    op.create_table(
        'data_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('source_type', sa.Enum('file', 'rest_api', name='sourcetype'), nullable=False),
        sa.Column('config', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.Enum('pending', 'active', 'error', name='sourcestatus'), nullable=False, server_default='pending'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id', name='pk_data_sources'),
    )

    op.create_table(
        'schemas',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('data_source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('columns', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('row_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('inferred_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['data_source_id'], ['data_sources.id'], name='fk_schemas_data_source_id_data_sources', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='pk_schemas'),
    )

    op.create_table(
        'profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('data_source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('statistics', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('null_rates', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('distributions', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('profiled_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['data_source_id'], ['data_sources.id'], name='fk_profiles_data_source_id_data_sources', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='pk_profiles'),
    )

    op.create_table(
        'insights',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('data_source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('insight_type', sa.Enum('anomaly', 'trend', 'forecast', 'pattern', 'summary', name='insighttype'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['data_source_id'], ['data_sources.id'], name='fk_insights_data_source_id_data_sources', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='pk_insights'),
    )

    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('insight_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['insight_id'], ['insights.id'], name='fk_notifications_insight_id_insights', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_notifications_user_id_users', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='pk_notifications'),
    )

    op.create_table(
        'agent_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('data_source_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('agent_name', sa.String(100), nullable=False),
        sa.Column('status', sa.Enum('running', 'success', 'error', name='agentstatus'), nullable=False),
        sa.Column('output_summary', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['data_source_id'], ['data_sources.id'], name='fk_agent_logs_data_source_id_data_sources', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name='pk_agent_logs'),
    )


def downgrade() -> None:
    op.drop_table('agent_logs')
    op.drop_table('notifications')
    op.drop_table('insights')
    op.drop_table('profiles')
    op.drop_table('schemas')
    op.drop_table('data_sources')
    op.drop_table('users')
    op.execute('DROP TYPE IF EXISTS agentstatus')
    op.execute('DROP TYPE IF EXISTS insighttype')
    op.execute('DROP TYPE IF EXISTS sourcestatus')
    op.execute('DROP TYPE IF EXISTS sourcetype')
    op.execute('DROP TYPE IF EXISTS userrole')
