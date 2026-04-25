"""User model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.security import AuthMethod


class User(Base):
    """User model for authentication."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    username: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
    )
    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    ssh_public_key: Mapped[str | None] = mapped_column(
        String(4096),
        nullable=True,
    )
    preferred_auth_method: Mapped[str] = mapped_column(
        String(50),
        default=AuthMethod.PASSWORD,
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    is_superuser: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )

    # Relationships
    repositories: Mapped[list["Repository"]] = relationship(  # noqa: F821
        back_populates="owner",
        lazy="selectin",
    )
    analyses: Mapped[list["Analysis"]] = relationship(  # noqa: F821
        back_populates="user",
        lazy="selectin",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(  # noqa: F821
        back_populates="user",
        lazy="selectin",
    )

    @property
    def has_password_auth(self) -> bool:
        """Check if password authentication is configured."""
        return self.password_hash is not None

    @property
    def has_ssh_auth(self) -> bool:
        """Check if SSH key authentication is configured."""
        return self.ssh_public_key is not None
