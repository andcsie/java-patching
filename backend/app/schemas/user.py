"""User schemas for API validation."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.core.security import AuthMethod


class UserBase(BaseModel):
    """Base user schema."""

    username: str = Field(..., min_length=3, max_length=255)
    email: EmailStr | None = None


class UserCreate(UserBase):
    """Schema for creating a user."""

    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Schema for user login."""

    username: str
    password: str


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    email: EmailStr | None = None
    password: str | None = Field(None, min_length=8, max_length=128)
    ssh_public_key: str | None = None
    preferred_auth_method: AuthMethod | None = None


class UserResponse(UserBase):
    """Schema for user responses."""

    id: uuid.UUID
    is_active: bool
    is_superuser: bool
    preferred_auth_method: str
    has_password_auth: bool
    has_ssh_auth: bool
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str
    exp: datetime
    type: str


class SSHChallengeRequest(BaseModel):
    """Request for SSH authentication challenge."""

    username: str


class SSHChallengeResponse(BaseModel):
    """Response with SSH authentication challenge."""

    challenge: str
    expires_at: datetime


class SSHVerifyRequest(BaseModel):
    """Request to verify SSH signature."""

    username: str
    challenge: str
    signature: str  # Base64 encoded signature
