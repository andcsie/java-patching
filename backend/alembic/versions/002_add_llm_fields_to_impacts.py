"""Add LLM fields to impacts table

Revision ID: 002
Revises: 001
Create Date: 2024-01-15 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to impacts table for LLM-generated content
    op.add_column(
        "impacts",
        sa.Column("llm_explanation", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "impacts",
        sa.Column("llm_fix", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "impacts",
        sa.Column("patch_content", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("impacts", "patch_content")
    op.drop_column("impacts", "llm_fix")
    op.drop_column("impacts", "llm_explanation")
