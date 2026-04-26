"""Pydantic schemas for trace API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TraceEventResponse(BaseModel):
    """Response schema for a trace event."""

    id: UUID
    trace_id: UUID
    parent_event_id: UUID | None = None
    agent: str
    event_type: str
    message: str
    data: dict = {}
    timestamp: datetime | None = None
    duration_ms: int | None = None
    llm_provider: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    decision: str | None = None
    reason: str | None = None
    confidence: int | None = None

    class Config:
        from_attributes = True


class TraceResponse(BaseModel):
    """Response schema for a trace."""

    id: UUID
    workflow_id: UUID
    repository_id: UUID | None = None
    user_id: UUID | None = None
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_events: int = 0
    total_decisions: int = 0
    total_llm_calls: int = 0
    total_errors: int = 0
    total_duration_ms: int | None = None
    extra_data: dict = {}

    class Config:
        from_attributes = True


class TraceWithEventsResponse(BaseModel):
    """Response schema for a trace with all events."""

    trace: TraceResponse
    events: list[TraceEventResponse]


class TraceSummary(BaseModel):
    """Summary of a trace for list views."""

    id: UUID
    workflow_id: UUID
    repository_id: UUID | None = None
    status: str
    started_at: datetime | None = None
    total_events: int = 0
    total_duration_ms: int | None = None

    class Config:
        from_attributes = True
