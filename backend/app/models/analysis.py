"""Analysis and Impact models."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ChangeType(StrEnum):
    """Types of JDK changes."""

    DEPRECATED = "deprecated"
    REMOVED = "removed"
    SECURITY = "security"
    BEHAVIORAL = "behavioral"
    BUGFIX = "bugfix"
    NEW_FEATURE = "new_feature"


class RiskLevel(StrEnum):
    """Risk levels for analysis."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnalysisStatus(StrEnum):
    """Analysis status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Analysis(Base):
    """Analysis model for JDK upgrade impact analysis."""

    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
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
    status: Mapped[str] = mapped_column(
        Enum(AnalysisStatus, name="analysis_status"),
        default=AnalysisStatus.PENDING,
    )
    risk_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    risk_level: Mapped[str | None] = mapped_column(
        Enum(RiskLevel, name="risk_level"),
        nullable=True,
    )
    total_files_analyzed: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    suggestions: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    llm_provider_used: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    repository: Mapped["Repository"] = relationship(  # noqa: F821
        back_populates="analyses",
    )
    user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="analyses",
    )
    impacts: Mapped[list["Impact"]] = relationship(
        back_populates="analysis",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class Impact(Base):
    """Impact model for individual code impacts."""

    __tablename__ = "impacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analyses.id"),
        nullable=False,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )
    line_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    column_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    change_type: Mapped[str] = mapped_column(
        Enum(ChangeType, name="change_type"),
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(
        Enum(RiskLevel, name="impact_severity"),
        nullable=False,
    )
    affected_code: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    affected_class: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    affected_method: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    jdk_component: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    cve_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    migration_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    suggested_fix: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    related_changes: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    analysis: Mapped["Analysis"] = relationship(
        back_populates="impacts",
    )
