"""Add traces and trace_events tables for agent observability.

Revision ID: 003
Revises: 002
Create Date: 2024-01-15 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create traces table
    op.create_table(
        "traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id"), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(20), default="running"),
        sa.Column("started_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("total_events", sa.Integer, default=0),
        sa.Column("total_decisions", sa.Integer, default=0),
        sa.Column("total_llm_calls", sa.Integer, default=0),
        sa.Column("total_errors", sa.Integer, default=0),
        sa.Column("total_duration_ms", sa.Integer, nullable=True),
        sa.Column("extra_data", postgresql.JSONB, default={}),
    )

    # Create trace_events table
    op.create_table(
        "trace_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("traces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("parent_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trace_events.id"), nullable=True),
        sa.Column("agent", sa.String(50), nullable=False, index=True),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("data", postgresql.JSONB, default={}),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.now(), index=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("llm_provider", sa.String(30), nullable=True),
        sa.Column("tokens_in", sa.Integer, nullable=True),
        sa.Column("tokens_out", sa.Integer, nullable=True),
        sa.Column("decision", sa.String(100), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("confidence", sa.Integer, nullable=True),
    )

    # Create indexes
    op.create_index("idx_traces_workflow", "traces", ["workflow_id"])
    op.create_index("idx_traces_repository", "traces", ["repository_id"])
    op.create_index("idx_trace_events_trace", "trace_events", ["trace_id"])
    op.create_index("idx_trace_events_agent", "trace_events", ["agent"])
    op.create_index("idx_trace_events_timestamp", "trace_events", ["timestamp"])


def downgrade() -> None:
    op.drop_index("idx_trace_events_timestamp")
    op.drop_index("idx_trace_events_agent")
    op.drop_index("idx_trace_events_trace")
    op.drop_index("idx_traces_repository")
    op.drop_index("idx_traces_workflow")
    op.drop_table("trace_events")
    op.drop_table("traces")
