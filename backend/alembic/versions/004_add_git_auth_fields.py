"""Add git authentication fields to repositories.

Revision ID: 004
Revises: 003
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add git provider and auth fields to repositories
    op.add_column('repositories', sa.Column('git_provider', sa.String(20), server_default='github', nullable=False))
    op.add_column('repositories', sa.Column('auth_method', sa.String(20), server_default='ssh', nullable=False))
    op.add_column('repositories', sa.Column('access_token', sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column('repositories', 'access_token')
    op.drop_column('repositories', 'auth_method')
    op.drop_column('repositories', 'git_provider')
