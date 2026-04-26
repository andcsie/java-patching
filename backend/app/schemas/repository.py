"""Repository schemas for API validation."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class GitProvider(str, Enum):
    """Supported git providers."""
    GITHUB = "github"
    BITBUCKET = "bitbucket"
    GITLAB = "gitlab"
    OTHER = "other"


class AuthMethod(str, Enum):
    """Repository authentication methods."""
    SSH = "ssh"
    PAT = "pat"
    NONE = "none"


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
    git_provider: GitProvider = GitProvider.GITHUB
    auth_method: AuthMethod = AuthMethod.SSH
    access_token: str | None = Field(None, description="Personal Access Token for HTTPS auth")


class RepositoryUpdate(BaseModel):
    """Schema for updating a repository."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    branch: str | None = None
    current_jdk_version: str | None = Field(None, pattern=r"^\d+\.\d+\.\d+$")
    target_jdk_version: str | None = Field(None, pattern=r"^\d+\.\d+\.\d+$")
    is_active: bool | None = None
    git_provider: GitProvider | None = None
    auth_method: AuthMethod | None = None
    access_token: str | None = Field(None, description="Personal Access Token (set to empty string to clear)")


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
    git_provider: str = "github"
    auth_method: str = "ssh"
    has_access_token: bool = False  # Don't expose actual token

    class Config:
        from_attributes = True

    @classmethod
    def model_validate(cls, obj, **kwargs):
        """Custom validation to compute has_access_token."""
        # Get the access_token from the ORM object
        access_token = getattr(obj, 'access_token', None)
        has_token = bool(access_token)

        # Create a dict from the object
        data = {
            "id": obj.id,
            "owner_id": obj.owner_id,
            "name": obj.name,
            "url": obj.url,
            "description": obj.description,
            "branch": obj.branch,
            "local_path": obj.local_path,
            "current_jdk_version": obj.current_jdk_version,
            "target_jdk_version": obj.target_jdk_version,
            "is_active": obj.is_active,
            "last_analyzed_at": obj.last_analyzed_at,
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
            "git_provider": getattr(obj, 'git_provider', 'github'),
            "auth_method": getattr(obj, 'auth_method', 'ssh'),
            "has_access_token": has_token,
        }
        return cls(**data)


class RepositoryCloneRequest(BaseModel):
    """Request to clone a repository."""

    repository_id: uuid.UUID


class RepositoryCloneResponse(BaseModel):
    """Response after cloning a repository."""

    repository_id: uuid.UUID
    local_path: str
    status: str
