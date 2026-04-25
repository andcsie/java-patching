"""Initial migration

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE analysis_status AS ENUM ('pending', 'running', 'completed', 'failed')")
    op.execute("CREATE TYPE risk_level AS ENUM ('low', 'medium', 'high', 'critical')")
    op.execute(
        "CREATE TYPE change_type AS ENUM "
        "('deprecated', 'removed', 'security', 'behavioral', 'bugfix', 'new_feature')"
    )

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("email", sa.String(255), unique=True, nullable=True, index=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("ssh_public_key", sa.String(4096), nullable=True),
        sa.Column("preferred_auth_method", sa.String(50), default="password"),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("is_superuser", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Create repositories table
    op.create_table(
        "repositories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("branch", sa.String(255), default="main"),
        sa.Column("local_path", sa.String(1024), nullable=True),
        sa.Column("current_jdk_version", sa.String(50), nullable=True),
        sa.Column("target_jdk_version", sa.String(50), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("last_analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Create analyses table
    op.create_table(
        "analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("from_version", sa.String(50), nullable=False),
        sa.Column("to_version", sa.String(50), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "completed", "failed", name="analysis_status"),
            default="pending",
        ),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column(
            "risk_level",
            sa.Enum("low", "medium", "high", "critical", name="risk_level"),
            nullable=True,
        ),
        sa.Column("total_files_analyzed", sa.Integer(), default=0),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("suggestions", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("llm_provider_used", sa.String(50), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create impacts table
    op.create_table(
        "impacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=True),
        sa.Column("column_number", sa.Integer(), nullable=True),
        sa.Column(
            "change_type",
            sa.Enum(
                "deprecated",
                "removed",
                "security",
                "behavioral",
                "bugfix",
                "new_feature",
                name="change_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum("low", "medium", "high", "critical", name="impact_severity"),
            nullable=False,
        ),
        sa.Column("affected_code", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("affected_class", sa.String(512), nullable=True),
        sa.Column("affected_method", sa.String(512), nullable=True),
        sa.Column("jdk_component", sa.String(255), nullable=True),
        sa.Column("cve_id", sa.String(50), nullable=True),
        sa.Column("migration_notes", sa.Text(), nullable=True),
        sa.Column("suggested_fix", sa.Text(), nullable=True),
        sa.Column("related_changes", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create audit_log table
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("action", sa.String(100), nullable=False, index=True),
        sa.Column("entity_type", sa.String(50), nullable=False, index=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )

    # Create analysis_history table
    op.create_table(
        "analysis_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("from_version", sa.String(50), nullable=False),
        sa.Column("to_version", sa.String(50), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("risk_level", sa.String(20), nullable=True),
        sa.Column("total_impacts", sa.Integer(), default=0),
        sa.Column("high_severity_count", sa.Integer(), default=0),
        sa.Column("medium_severity_count", sa.Integer(), default=0),
        sa.Column("low_severity_count", sa.Integer(), default=0),
        sa.Column("full_report", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("analysis_history")
    op.drop_table("audit_log")
    op.drop_table("impacts")
    op.drop_table("analyses")
    op.drop_table("repositories")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS change_type")
    op.execute("DROP TYPE IF EXISTS risk_level")
    op.execute("DROP TYPE IF EXISTS analysis_status")
    op.execute("DROP TYPE IF EXISTS impact_severity")
