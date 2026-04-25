"""Repository model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Repository(Base):
    """Repository model for tracked Java projects."""

    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    branch: Mapped[str] = mapped_column(
        String(255),
        default="main",
    )
    local_path: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )
    current_jdk_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    target_jdk_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    last_analyzed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )

    # Relationships
    owner: Mapped["User"] = relationship(  # noqa: F821
        back_populates="repositories",
    )
    analyses: Mapped[list["Analysis"]] = relationship(  # noqa: F821
        back_populates="repository",
        lazy="selectin",
    )
