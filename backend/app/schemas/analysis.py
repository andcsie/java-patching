"""Analysis schemas for API validation."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.analysis import AnalysisStatus, ChangeType, RiskLevel


class AnalysisCreate(BaseModel):
    """Schema for creating an analysis."""

    repository_id: uuid.UUID
    from_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    to_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    llm_provider: str | None = None


class AnalysisUpdate(BaseModel):
    """Schema for updating an analysis."""

    status: AnalysisStatus | None = None


class ImpactResponse(BaseModel):
    """Schema for impact responses."""

    id: uuid.UUID
    analysis_id: uuid.UUID
    file_path: str
    line_number: int | None
    column_number: int | None
    change_type: ChangeType
    severity: RiskLevel
    affected_code: str | None
    description: str
    affected_class: str | None
    affected_method: str | None
    jdk_component: str | None
    cve_id: str | None
    migration_notes: str | None
    suggested_fix: str | None
    related_changes: list[str] | None
    created_at: datetime

    class Config:
        from_attributes = True


class AnalysisResponse(BaseModel):
    """Schema for analysis responses."""

    id: uuid.UUID
    repository_id: uuid.UUID
    user_id: uuid.UUID
    from_version: str
    to_version: str
    status: AnalysisStatus
    risk_score: int | None
    risk_level: RiskLevel | None
    total_files_analyzed: int
    summary: str | None
    suggestions: dict | None
    error_message: str | None
    llm_provider_used: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    impacts: list[ImpactResponse] | None = None

    class Config:
        from_attributes = True


class AnalysisSummary(BaseModel):
    """Summary of an analysis."""

    id: uuid.UUID
    repository_id: uuid.UUID
    from_version: str
    to_version: str
    status: AnalysisStatus
    risk_score: int | None
    risk_level: RiskLevel | None
    total_impacts: int
    high_severity_count: int
    medium_severity_count: int
    low_severity_count: int
    created_at: datetime


class JDKChangeInfo(BaseModel):
    """Information about a JDK change."""

    version: str
    change_type: ChangeType
    component: str
    description: str
    affected_classes: list[str]
    affected_methods: list[str]
    cve_id: str | None = None
    migration_notes: str | None = None
