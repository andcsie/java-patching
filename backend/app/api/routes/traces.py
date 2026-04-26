"""API routes for trace observability."""

import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from app.schemas.trace import (
    TraceEventResponse,
    TraceResponse,
    TraceSummary,
    TraceWithEventsResponse,
)
from app.services.trace_service import trace_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/traces", tags=["traces"])


@router.get("", response_model=list[TraceSummary])
async def list_traces(
    repository_id: UUID | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """List recent traces."""
    traces = await trace_service.get_recent_traces(
        repository_id=repository_id,
        limit=limit,
    )
    return [TraceSummary.model_validate(t) for t in traces]


@router.get("/{trace_id}", response_model=TraceResponse)
async def get_trace(trace_id: UUID):
    """Get a trace by ID."""
    trace = await trace_service.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return TraceResponse.model_validate(trace)


@router.get("/{trace_id}/events", response_model=list[TraceEventResponse])
async def get_trace_events(trace_id: UUID):
    """Get all events for a trace."""
    events = await trace_service.get_events(trace_id)
    return [TraceEventResponse.model_validate(e) for e in events]


@router.get("/{trace_id}/full", response_model=TraceWithEventsResponse)
async def get_trace_with_events(trace_id: UUID):
    """Get a trace with all its events."""
    trace = await trace_service.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")

    events = await trace_service.get_events(trace_id)

    return TraceWithEventsResponse(
        trace=TraceResponse.model_validate(trace),
        events=[TraceEventResponse.model_validate(e) for e in events],
    )


@router.get("/workflow/{workflow_id}", response_model=TraceResponse)
async def get_trace_by_workflow(workflow_id: UUID):
    """Get the most recent trace for a workflow."""
    trace = await trace_service.get_trace_by_workflow(workflow_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return TraceResponse.model_validate(trace)


# -------------------------------------------------------------------------
# WebSocket for real-time events
# -------------------------------------------------------------------------

class ConnectionManager:
    """Manage WebSocket connections for trace streaming."""

    def __init__(self):
        self.active_connections: dict[UUID, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, workflow_id: UUID):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            if workflow_id not in self.active_connections:
                self.active_connections[workflow_id] = []
            self.active_connections[workflow_id].append(websocket)

        logger.info(f"[WS] Client connected for workflow {workflow_id}")

    async def disconnect(self, websocket: WebSocket, workflow_id: UUID):
        """Remove a WebSocket connection."""
        async with self._lock:
            if workflow_id in self.active_connections:
                try:
                    self.active_connections[workflow_id].remove(websocket)
                    if not self.active_connections[workflow_id]:
                        del self.active_connections[workflow_id]
                except ValueError:
                    pass

        logger.info(f"[WS] Client disconnected from workflow {workflow_id}")

    async def broadcast(self, workflow_id: UUID, message: dict):
        """Broadcast a message to all connections for a workflow."""
        async with self._lock:
            connections = self.active_connections.get(workflow_id, []).copy()

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"[WS] Failed to send message: {e}")


manager = ConnectionManager()


@router.websocket("/ws/{workflow_id}")
async def trace_websocket(websocket: WebSocket, workflow_id: UUID):
    """WebSocket endpoint for real-time trace events."""
    await manager.connect(websocket, workflow_id)

    # Create callback for trace service
    async def on_event(event: dict):
        await manager.broadcast(workflow_id, {
            "type": "trace_event",
            "event": event,
        })

    # Subscribe to trace events
    await trace_service.subscribe(workflow_id, on_event)

    try:
        # Send initial state
        trace = await trace_service.get_trace_by_workflow(workflow_id)
        if trace:
            events = await trace_service.get_events(trace.id)
            await websocket.send_json({
                "type": "initial_state",
                "trace": {
                    "id": str(trace.id),
                    "status": trace.status,
                    "started_at": trace.started_at.isoformat() if trace.started_at else None,
                },
                "events": [e.to_dict() for e in events],
            })

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages (ping/pong or commands)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)

                # Handle ping
                if data == "ping":
                    await websocket.send_text("pong")

            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info(f"[WS] Client disconnected from workflow {workflow_id}")
    except Exception as e:
        logger.error(f"[WS] Error in WebSocket handler: {e}")
    finally:
        await trace_service.unsubscribe(workflow_id, on_event)
        await manager.disconnect(websocket, workflow_id)
