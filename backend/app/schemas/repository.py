"""Repository schemas for API validation."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class RepositoryBase(BaseModel):
    """Base repository schema."""

    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., max_length=1024)
    description: str | None = None
    branch: str = "main"


class RepositoryCreate(RepositoryBase):
    """Schema for creating a repository."""

    current_jdk_version: str | None = Field(None, pattern=r"^\d+\.\d+\.\d+$")
    target_jdk_version: str | None = Field(None, pattern=r"^\d+\.\d+\.\d+$")


class RepositoryUpdate(BaseModel):
    """Schema for updating a repository."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    branch: str | None = None
    current_jdk_version: str | None = Field(None, pattern=r"^\d+\.\d+\.\d+$")
    target_jdk_version: str | None = Field(None, pattern=r"^\d+\.\d+\.\d+$")
    is_active: bool | None = None


class RepositoryResponse(RepositoryBase):
    """Schema for repository responses."""

    id: uuid.UUID
    owner_id: uuid.UUID
    local_path: str | None
    current_jdk_version: str | None
    target_jdk_version: str | None
    is_active: bool
    last_analyzed_at: datetime | None
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class RepositoryCloneRequest(BaseModel):
    """Request to clone a repository."""

    repository_id: uuid.UUID


class RepositoryCloneResponse(BaseModel):
    """Response after cloning a repository."""

    repository_id: uuid.UUID
    local_path: str
    status: str
