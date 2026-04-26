"""Trace and TraceEvent models for agent observability."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class TraceStatus(str, Enum):
    """Status of a trace."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EventType(str, Enum):
    """Type of trace event."""
    INFO = "info"
    ACTION = "action"
    DECISION = "decision"
    LLM_CALL = "llm_call"
    ERROR = "error"
    WARNING = "warning"


class Trace(Base):
    """A trace represents a complete workflow execution."""

    __tablename__ = "traces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    status = Column(String(20), default=TraceStatus.RUNNING.value)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Summary data
    total_events = Column(Integer, default=0)
    total_decisions = Column(Integer, default=0)
    total_llm_calls = Column(Integer, default=0)
    total_errors = Column(Integer, default=0)
    total_duration_ms = Column(Integer, nullable=True)

    extra_data = Column(JSONB, default=dict)

    # Relationships
    events = relationship("TraceEvent", back_populates="trace", cascade="all, delete-orphan")
    repository = relationship("Repository", back_populates="traces")
    user = relationship("User", back_populates="traces")

    def __repr__(self):
        return f"<Trace {self.id} workflow={self.workflow_id} status={self.status}>"


class TraceEvent(Base):
    """A single event within a trace."""

    __tablename__ = "trace_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(UUID(as_uuid=True), ForeignKey("traces.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_event_id = Column(UUID(as_uuid=True), ForeignKey("trace_events.id"), nullable=True)

    agent = Column(String(50), nullable=False, index=True)
    event_type = Column(String(30), nullable=False)
    message = Column(Text, nullable=False)

    # Detailed data
    data = Column(JSONB, default=dict)

    # Timing
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    duration_ms = Column(Integer, nullable=True)

    # For LLM calls
    llm_provider = Column(String(30), nullable=True)
    tokens_in = Column(Integer, nullable=True)
    tokens_out = Column(Integer, nullable=True)

    # For decisions
    decision = Column(String(100), nullable=True)
    reason = Column(Text, nullable=True)
    confidence = Column(Integer, nullable=True)  # 0-100

    # Relationships
    trace = relationship("Trace", back_populates="events")
    children = relationship("TraceEvent", backref="parent", remote_side=[id])

    def __repr__(self):
        return f"<TraceEvent {self.id} agent={self.agent} type={self.event_type}>"

    def to_dict(self) -> dict:
        """Convert to dictionary for WebSocket/API responses."""
        return {
            "id": str(self.id),
            "trace_id": str(self.trace_id),
            "parent_event_id": str(self.parent_event_id) if self.parent_event_id else None,
            "agent": self.agent,
            "event_type": self.event_type,
            "message": self.message,
            "data": self.data or {},
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "duration_ms": self.duration_ms,
            "llm_provider": self.llm_provider,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "decision": self.decision,
            "reason": self.reason,
            "confidence": self.confidence,
        }
