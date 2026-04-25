"""Audit schemas for API validation."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


class AuditLogResponse(BaseModel):
    """Schema for audit log responses."""

    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    details: dict | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime

    class Config:
        from_attributes = True

    @field_validator("ip_address", mode="before")
    @classmethod
    def convert_ip_address(cls, v: Any) -> str | None:
        """Convert IP address to string."""
        if v is None:
            return None
        return str(v)


class AuditLogQuery(BaseModel):
    """Query parameters for audit log search."""

    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    action: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    limit: int = 100
    offset: int = 0


class AnalysisHistoryResponse(BaseModel):
    """Schema for analysis history responses."""

    id: uuid.UUID
    analysis_id: uuid.UUID
    repository_id: uuid.UUID
    user_id: uuid.UUID
    from_version: str
    to_version: str
    risk_score: int | None
    risk_level: str | None
    total_impacts: int
    high_severity_count: int
    medium_severity_count: int
    low_severity_count: int
    full_report: dict | None
    created_at: datetime

    class Config:
        from_attributes = True


class AnalysisHistoryQuery(BaseModel):
    """Query parameters for analysis history search."""

    repository_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    from_version: str | None = None
    to_version: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    limit: int = 100
    offset: int = 0
