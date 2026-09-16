"""Initial schema creation.

Revision ID: 001_initial_schema
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema."""
    # Enable extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS postgis')
    op.execute('CREATE EXTENSION IF NOT EXISTS pgvector')

    # Create organisation table
    op.create_table(
        'organisation',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('country', sa.String(2), nullable=False, server_default='NG'),
        sa.Column('timezone', sa.String(50), nullable=False, server_default='Africa/Lagos'),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('website', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('metadata', postgresql.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('code'),
    )
    op.create_index('idx_organisation_code', 'organisation', ['code'])
    op.create_index('idx_organisation_active', 'organisation', ['is_active'])

    # Create user table
    op.create_table(
        'user',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_login', sa.String(), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('timezone', sa.String(50), nullable=True),
        sa.Column('language', sa.String(5), nullable=False, server_default='en'),
        sa.Column('preferences', postgresql.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('idx_user_email', 'user', ['email'])
    op.create_index('idx_user_active', 'user', ['is_active'])


def downgrade() -> None:
    """Drop initial schema."""
    op.drop_index('idx_user_active', table_name='user')
    op.drop_index('idx_user_email', table_name='user')
    op.drop_table('user')
    op.drop_index('idx_organisation_active', table_name='organisation')
    op.drop_index('idx_organisation_code', table_name='organisation')
    op.drop_table('organisation')
