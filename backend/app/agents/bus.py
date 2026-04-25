"""Agent communication bus for inter-agent messaging."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """Types of messages agents can send."""
    REQUEST = "request"          # Request another agent to do something
    RESPONSE = "response"        # Response to a request
    EVENT = "event"              # Broadcast event (no response expected)
    ERROR = "error"              # Error notification


@dataclass
class AgentMessage:
    """Message passed between agents."""
    id: UUID = field(default_factory=uuid4)
    type: MessageType = MessageType.EVENT
    from_agent: str = ""
    to_agent: str | None = None  # None = broadcast
    action: str = ""
    payload: dict = field(default_factory=dict)
    correlation_id: UUID | None = None  # Links request/response
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WorkflowContext:
    """Shared context for a workflow execution.

    Agents read from and write to this context.
    This is the "blackboard" pattern for agent communication.
    """
    workflow_id: UUID = field(default_factory=uuid4)
    repository_path: str = ""
    from_version: str = ""
    to_version: str = ""
    user_id: UUID | None = None

    # Results from each stage (agents write here)
    scan_result: dict | None = None
    release_notes: list[dict] = field(default_factory=list)
    impacts: list[dict] = field(default_factory=list)
    explanations: list[dict] = field(default_factory=list)
    fixes: list[dict] = field(default_factory=list)
    patches: list[dict] = field(default_factory=list)
    version_bumps: list[dict] = field(default_factory=list)

    # Metadata
    risk_score: int = 0
    risk_level: str = "unknown"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Tracking
    completed_stages: list[str] = field(default_factory=list)
    current_stage: str = ""
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


class AgentBus:
    """Message bus for agent communication.

    Supports:
    - Direct messaging between agents
    - Broadcast events
    - Request/response patterns
    - Event subscriptions
    """

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}
        self._pending_responses: dict[UUID, asyncio.Future] = {}
        self._message_history: list[AgentMessage] = []
        self._workflows: dict[UUID, WorkflowContext] = {}

    def subscribe(
        self,
        event_pattern: str,
        handler: Callable[[AgentMessage, WorkflowContext | None], Coroutine],
    ) -> None:
        """Subscribe to events matching a pattern.

        Patterns:
        - "scan.complete" - specific event
        - "scan.*" - all scan events
        - "*" - all events
        """
        if event_pattern not in self._handlers:
            self._handlers[event_pattern] = []
        self._handlers[event_pattern].append(handler)
        logger.debug(f"[AgentBus] Subscribed to '{event_pattern}'")

    async def publish(
        self,
        message: AgentMessage,
        workflow_id: UUID | None = None,
    ) -> None:
        """Publish a message to the bus."""
        self._message_history.append(message)

        workflow = self._workflows.get(workflow_id) if workflow_id else None
        event_name = f"{message.from_agent}.{message.action}"

        logger.info(f"[AgentBus] Publishing: {event_name}")

        # Find matching handlers
        handlers_to_call = []

        # Exact match
        if event_name in self._handlers:
            handlers_to_call.extend(self._handlers[event_name])

        # Wildcard match (agent.*)
        agent_wildcard = f"{message.from_agent}.*"
        if agent_wildcard in self._handlers:
            handlers_to_call.extend(self._handlers[agent_wildcard])

        # Global wildcard
        if "*" in self._handlers:
            handlers_to_call.extend(self._handlers["*"])

        # Call handlers
        for handler in handlers_to_call:
            try:
                await handler(message, workflow)
            except Exception as e:
                logger.error(f"[AgentBus] Handler error: {e}")

    async def request(
        self,
        from_agent: str,
        to_agent: str,
        action: str,
        payload: dict,
        workflow_id: UUID | None = None,
        timeout: float = 60.0,
    ) -> AgentMessage:
        """Send a request and wait for response."""
        request_id = uuid4()

        message = AgentMessage(
            id=request_id,
            type=MessageType.REQUEST,
            from_agent=from_agent,
            to_agent=to_agent,
            action=action,
            payload=payload,
        )

        # Create future for response
        future: asyncio.Future = asyncio.Future()
        self._pending_responses[request_id] = future

        # Publish request
        await self.publish(message, workflow_id)

        # Wait for response
        try:
            response = await asyncio.wait_for(future, timeout)
            return response
        except asyncio.TimeoutError:
            del self._pending_responses[request_id]
            return AgentMessage(
                type=MessageType.ERROR,
                from_agent="bus",
                to_agent=from_agent,
                action="timeout",
                payload={"error": f"Request to {to_agent}.{action} timed out"},
                correlation_id=request_id,
            )

    async def respond(
        self,
        to_message: AgentMessage,
        from_agent: str,
        payload: dict,
        workflow_id: UUID | None = None,
    ) -> None:
        """Send a response to a request."""
        response = AgentMessage(
            type=MessageType.RESPONSE,
            from_agent=from_agent,
            to_agent=to_message.from_agent,
            action=f"{to_message.action}_response",
            payload=payload,
            correlation_id=to_message.id,
        )

        # Resolve pending future if exists
        if to_message.id in self._pending_responses:
            self._pending_responses[to_message.id].set_result(response)
            del self._pending_responses[to_message.id]

        await self.publish(response, workflow_id)

    # Workflow management
    def create_workflow(
        self,
        repository_path: str,
        from_version: str,
        to_version: str,
        user_id: UUID | None = None,
    ) -> WorkflowContext:
        """Create a new workflow context."""
        workflow = WorkflowContext(
            repository_path=repository_path,
            from_version=from_version,
            to_version=to_version,
            user_id=user_id,
        )
        self._workflows[workflow.workflow_id] = workflow
        logger.info(f"[AgentBus] Created workflow {workflow.workflow_id}")
        return workflow

    def get_workflow(self, workflow_id: UUID) -> WorkflowContext | None:
        """Get a workflow by ID."""
        return self._workflows.get(workflow_id)

    def complete_workflow(self, workflow_id: UUID) -> None:
        """Mark a workflow as complete."""
        if workflow_id in self._workflows:
            self._workflows[workflow_id].completed_at = datetime.utcnow()
            logger.info(f"[AgentBus] Completed workflow {workflow_id}")


# Global bus instance
agent_bus = AgentBus()
