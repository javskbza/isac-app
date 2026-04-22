"""v2 schema — users extensions, new tables, sourcestatus enum additions

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-22 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. New enum types
    # ------------------------------------------------------------------
    userstatus = postgresql.ENUM('active', 'disabled', name='userstatus', create_type=False)
    userstatus.create(op.get_bind(), checkfirst=True)

    themepref = postgresql.ENUM('light', 'dark', 'system', name='themepref', create_type=False)
    themepref.create(op.get_bind(), checkfirst=True)

    auditaction = postgresql.ENUM(
        'create', 'modify_email', 'modify_role', 'modify_status', 'reset_password', 'delete',
        name='auditaction', create_type=False,
    )
    auditaction.create(op.get_bind(), checkfirst=True)

    pollstatus = postgresql.ENUM('success', 'failure', name='pollstatus', create_type=False)
    pollstatus.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # 2. Extend sourcestatus enum (PostgreSQL 15 allows this in a transaction)
    # ------------------------------------------------------------------
    op.execute("ALTER TYPE sourcestatus ADD VALUE IF NOT EXISTS 'degraded'")
    op.execute("ALTER TYPE sourcestatus ADD VALUE IF NOT EXISTS 'paused'")
    op.execute("ALTER TYPE sourcestatus ADD VALUE IF NOT EXISTS 'disconnected'")

    # ------------------------------------------------------------------
    # 3. users table — add status + new columns, migrate data, drop is_active
    # ------------------------------------------------------------------
    op.add_column('users',
        sa.Column('status', postgresql.ENUM('active', 'disabled', name='userstatus', create_type=False),
                  nullable=False, server_default='active')
    )
    # Migrate existing rows: disabled users (is_active=false) → status='disabled'
    op.execute("UPDATE users SET status = 'disabled' WHERE is_active = false")
    op.drop_column('users', 'is_active')

    op.add_column('users',
        sa.Column('updated_at', sa.DateTime(), nullable=True)
    )
    op.add_column('users',
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column('users',
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column('users',
        sa.Column('password_updated_at', sa.DateTime(), nullable=True)
    )
    op.add_column('users',
        sa.Column('theme_preference',
                  postgresql.ENUM('light', 'dark', 'system', name='themepref', create_type=False),
                  nullable=False, server_default='light')
    )
    op.add_column('users',
        sa.Column('last_selected_source_id', postgresql.UUID(as_uuid=True), nullable=True)
    )

    op.create_foreign_key(
        'fk_users_created_by_users', 'users', 'users', ['created_by'], ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_users_updated_by_users', 'users', 'users', ['updated_by'], ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_users_last_selected_source_id_data_sources',
        'users', 'data_sources',
        ['last_selected_source_id'], ['id'],
        ondelete='SET NULL',
    )

    # ------------------------------------------------------------------
    # 4. user_audit_log
    # ------------------------------------------------------------------
    op.create_table(
        'user_audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('actor_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('actor_email', sa.String(255), nullable=False),
        sa.Column('target_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('target_email', sa.String(255), nullable=False),
        sa.Column('action',
                  postgresql.ENUM('create', 'modify_email', 'modify_role', 'modify_status',
                          'reset_password', 'delete', name='auditaction', create_type=False),
                  nullable=False),
        sa.Column('before_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('after_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'],
                                name='fk_audit_log_actor_user_id', ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['target_user_id'], ['users.id'],
                                name='fk_audit_log_target_user_id', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name='pk_user_audit_log'),
    )
    op.create_index('ix_user_audit_log_actor_ts', 'user_audit_log',
                    ['actor_user_id', 'timestamp'])
    op.create_index('ix_user_audit_log_target_ts', 'user_audit_log',
                    ['target_user_id', 'timestamp'])
    op.create_index('ix_user_audit_log_action_ts', 'user_audit_log',
                    ['action', 'timestamp'])

    # ------------------------------------------------------------------
    # 5. user_dashboard_layouts
    # ------------------------------------------------------------------
    op.create_table(
        'user_dashboard_layouts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('layout', postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  server_default='{}'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'],
                                name='fk_dashboard_layouts_user_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='pk_user_dashboard_layouts'),
        sa.UniqueConstraint('user_id', name='uq_dashboard_layouts_user_id'),
    )

    # ------------------------------------------------------------------
    # 6. source_schedules
    # ------------------------------------------------------------------
    op.create_table(
        'source_schedules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('schedule_expr', sa.String(100), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['data_sources.id'],
                                name='fk_source_schedules_source_id', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'],
                                name='fk_source_schedules_created_by', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name='pk_source_schedules'),
        sa.UniqueConstraint('source_id', name='uq_source_schedules_source_id'),
    )

    # ------------------------------------------------------------------
    # 7. source_poll_log
    # ------------------------------------------------------------------
    op.create_table(
        'source_poll_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('status', postgresql.ENUM('success', 'failure', name='pollstatus', create_type=False), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['data_sources.id'],
                                name='fk_source_poll_log_source_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='pk_source_poll_log'),
    )
    op.create_index('ix_source_poll_log_source_started', 'source_poll_log',
                    ['source_id', 'started_at'])


def downgrade() -> None:
    op.drop_table('source_poll_log')
    op.drop_table('source_schedules')
    op.drop_table('user_dashboard_layouts')
    op.drop_table('user_audit_log')

    op.drop_constraint('fk_users_last_selected_source_id_data_sources', 'users', type_='foreignkey')
    op.drop_constraint('fk_users_updated_by_users', 'users', type_='foreignkey')
    op.drop_constraint('fk_users_created_by_users', 'users', type_='foreignkey')

    op.drop_column('users', 'last_selected_source_id')
    op.drop_column('users', 'theme_preference')
    op.drop_column('users', 'password_updated_at')
    op.drop_column('users', 'updated_by')
    op.drop_column('users', 'created_by')
    op.drop_column('users', 'updated_at')

    # Restore is_active from status before dropping status
    op.add_column('users',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true')
    )
    op.execute("UPDATE users SET is_active = false WHERE status = 'disabled'")
    op.drop_column('users', 'status')

    op.execute('DROP TYPE IF EXISTS pollstatus')
    op.execute('DROP TYPE IF EXISTS auditaction')
    op.execute('DROP TYPE IF EXISTS themepref')
    op.execute('DROP TYPE IF EXISTS userstatus')
    # NOTE: sourcestatus enum values (degraded, paused, disconnected) cannot be removed
    # in PostgreSQL. They are left in place after downgrade.
