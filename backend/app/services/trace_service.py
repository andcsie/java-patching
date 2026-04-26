"""Trace service for agent observability and real-time event streaming."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Callable
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.models.trace import EventType, Trace, TraceEvent, TraceStatus

logger = logging.getLogger(__name__)


class TraceService:
    """Service for managing traces and events with real-time broadcasting."""

    def __init__(self):
        # Subscribers for real-time updates: {workflow_id: [callback, ...]}
        self._subscribers: dict[UUID, list[Callable]] = {}
        self._lock = asyncio.Lock()

    # -------------------------------------------------------------------------
    # Trace Lifecycle
    # -------------------------------------------------------------------------

    async def start_trace(
        self,
        workflow_id: UUID,
        repository_id: UUID | None = None,
        user_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> Trace:
        """Start a new trace for a workflow execution."""
        async with async_session_maker() as session:
            trace = Trace(
                workflow_id=workflow_id,
                repository_id=repository_id,
                user_id=user_id,
                status=TraceStatus.RUNNING.value,
                extra_data=metadata or {},
            )
            session.add(trace)
            await session.commit()
            await session.refresh(trace)

            logger.info(f"[Trace] Started trace {trace.id} for workflow {workflow_id}")
            return trace

    async def end_trace(
        self,
        trace_id: UUID,
        status: TraceStatus = TraceStatus.COMPLETED,
    ) -> None:
        """End a trace and calculate summary statistics."""
        async with async_session_maker() as session:
            # Get event counts
            result = await session.execute(
                select(TraceEvent).where(TraceEvent.trace_id == trace_id)
            )
            events = result.scalars().all()

            total_events = len(events)
            total_decisions = sum(1 for e in events if e.event_type == EventType.DECISION.value)
            total_llm_calls = sum(1 for e in events if e.event_type == EventType.LLM_CALL.value)
            total_errors = sum(1 for e in events if e.event_type == EventType.ERROR.value)

            # Calculate total duration
            if events:
                start_time = min(e.timestamp for e in events if e.timestamp)
                end_time = max(e.timestamp for e in events if e.timestamp)
                total_duration_ms = int((end_time - start_time).total_seconds() * 1000)
            else:
                total_duration_ms = 0

            await session.execute(
                update(Trace)
                .where(Trace.id == trace_id)
                .values(
                    status=status.value,
                    completed_at=datetime.utcnow(),
                    total_events=total_events,
                    total_decisions=total_decisions,
                    total_llm_calls=total_llm_calls,
                    total_errors=total_errors,
                    total_duration_ms=total_duration_ms,
                )
            )
            await session.commit()

            logger.info(f"[Trace] Ended trace {trace_id} with status {status.value}")

    async def get_trace(self, trace_id: UUID) -> Trace | None:
        """Get a trace by ID."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Trace).where(Trace.id == trace_id)
            )
            return result.scalar_one_or_none()

    async def get_trace_by_workflow(self, workflow_id: UUID) -> Trace | None:
        """Get the most recent trace for a workflow."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Trace)
                .where(Trace.workflow_id == workflow_id)
                .order_by(Trace.started_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def get_events(self, trace_id: UUID) -> list[TraceEvent]:
        """Get all events for a trace."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(TraceEvent)
                .where(TraceEvent.trace_id == trace_id)
                .order_by(TraceEvent.timestamp)
            )
            return list(result.scalars().all())

    # -------------------------------------------------------------------------
    # Event Logging
    # -------------------------------------------------------------------------

    async def log_event(
        self,
        trace_id: UUID,
        agent: str,
        event_type: EventType | str,
        message: str,
        data: dict | None = None,
        duration_ms: int | None = None,
        parent_event_id: UUID | None = None,
    ) -> TraceEvent:
        """Log a generic event."""
        if isinstance(event_type, EventType):
            event_type = event_type.value

        async with async_session_maker() as session:
            event = TraceEvent(
                trace_id=trace_id,
                agent=agent,
                event_type=event_type,
                message=message,
                data=data or {},
                duration_ms=duration_ms,
                parent_event_id=parent_event_id,
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)

            # Broadcast to subscribers
            await self._broadcast(trace_id, event)

            return event

    async def log_info(
        self,
        trace_id: UUID,
        agent: str,
        message: str,
        data: dict | None = None,
    ) -> TraceEvent:
        """Log an informational event."""
        return await self.log_event(
            trace_id=trace_id,
            agent=agent,
            event_type=EventType.INFO,
            message=message,
            data=data,
        )

    async def log_action(
        self,
        trace_id: UUID,
        agent: str,
        action: str,
        params: dict | None = None,
        duration_ms: int | None = None,
    ) -> TraceEvent:
        """Log an agent action."""
        return await self.log_event(
            trace_id=trace_id,
            agent=agent,
            event_type=EventType.ACTION,
            message=f"Executing {action}",
            data={"action": action, "params": params or {}},
            duration_ms=duration_ms,
        )

    async def log_decision(
        self,
        trace_id: UUID,
        agent: str,
        decision: str,
        reason: str,
        confidence: int | None = None,
        evidence: dict | None = None,
    ) -> TraceEvent:
        """Log a decision with explanation."""
        async with async_session_maker() as session:
            event = TraceEvent(
                trace_id=trace_id,
                agent=agent,
                event_type=EventType.DECISION.value,
                message=f"Decision: {decision}",
                data={"evidence": evidence or {}},
                decision=decision,
                reason=reason,
                confidence=confidence,
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)

            await self._broadcast(trace_id, event)
            return event

    async def log_llm_call(
        self,
        trace_id: UUID,
        agent: str,
        provider: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: int,
        prompt_summary: str | None = None,
        response_summary: str | None = None,
    ) -> TraceEvent:
        """Log an LLM API call."""
        async with async_session_maker() as session:
            event = TraceEvent(
                trace_id=trace_id,
                agent=agent,
                event_type=EventType.LLM_CALL.value,
                message=f"LLM call to {provider}/{model}",
                data={
                    "model": model,
                    "prompt_summary": prompt_summary,
                    "response_summary": response_summary,
                },
                llm_provider=provider,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                duration_ms=latency_ms,
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)

            await self._broadcast(trace_id, event)
            return event

    async def log_error(
        self,
        trace_id: UUID,
        agent: str,
        error: str,
        details: dict | None = None,
    ) -> TraceEvent:
        """Log an error event."""
        return await self.log_event(
            trace_id=trace_id,
            agent=agent,
            event_type=EventType.ERROR,
            message=f"Error: {error}",
            data={"error": error, "details": details or {}},
        )

    async def log_warning(
        self,
        trace_id: UUID,
        agent: str,
        warning: str,
        details: dict | None = None,
    ) -> TraceEvent:
        """Log a warning event."""
        return await self.log_event(
            trace_id=trace_id,
            agent=agent,
            event_type=EventType.WARNING,
            message=f"Warning: {warning}",
            data={"warning": warning, "details": details or {}},
        )

    # -------------------------------------------------------------------------
    # Real-time Subscriptions
    # -------------------------------------------------------------------------

    async def subscribe(self, workflow_id: UUID, callback: Callable) -> None:
        """Subscribe to real-time events for a workflow."""
        async with self._lock:
            if workflow_id not in self._subscribers:
                self._subscribers[workflow_id] = []
            self._subscribers[workflow_id].append(callback)
            logger.debug(f"[Trace] Subscribed to workflow {workflow_id}")

    async def unsubscribe(self, workflow_id: UUID, callback: Callable) -> None:
        """Unsubscribe from workflow events."""
        async with self._lock:
            if workflow_id in self._subscribers:
                try:
                    self._subscribers[workflow_id].remove(callback)
                    if not self._subscribers[workflow_id]:
                        del self._subscribers[workflow_id]
                except ValueError:
                    pass

    async def _broadcast(self, trace_id: UUID, event: TraceEvent) -> None:
        """Broadcast an event to all subscribers."""
        # Get workflow_id from trace
        trace = await self.get_trace(trace_id)
        if not trace:
            return

        workflow_id = trace.workflow_id

        async with self._lock:
            callbacks = self._subscribers.get(workflow_id, []).copy()

        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event.to_dict())
                else:
                    callback(event.to_dict())
            except Exception as e:
                logger.warning(f"[Trace] Broadcast callback failed: {e}")

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    async def get_recent_traces(
        self,
        user_id: UUID | None = None,
        repository_id: UUID | None = None,
        limit: int = 20,
    ) -> list[Trace]:
        """Get recent traces with optional filters."""
        async with async_session_maker() as session:
            query = select(Trace).order_by(Trace.started_at.desc()).limit(limit)

            if user_id:
                query = query.where(Trace.user_id == user_id)
            if repository_id:
                query = query.where(Trace.repository_id == repository_id)

            result = await session.execute(query)
            return list(result.scalars().all())


# Global instance
trace_service = TraceService()
