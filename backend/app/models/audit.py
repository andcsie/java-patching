"""Audit models for logging and history."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AuditLog(Base):
    """Audit log for tracking all significant actions."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    details: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    ip_address: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="audit_logs",
    )


class AnalysisHistory(Base):
    """Historical analyses for audit trail (never deleted)."""

    __tablename__ = "analysis_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    from_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    to_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    risk_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    risk_level: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    total_impacts: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    high_severity_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    medium_severity_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    low_severity_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    full_report: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
