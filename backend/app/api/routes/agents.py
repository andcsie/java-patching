"""API routes for multi-agent system."""

import logging
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.agents import AgentCapability, AgentContext, agent_registry

logger = logging.getLogger(__name__)
from app.api.deps import CurrentUser, DbSession
from app.services.audit_service import AuditService
from app.services.repository_service import RepositoryService

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class AgentInfo(BaseModel):
    """Information about an agent."""

    name: str
    description: str
    version: str
    capabilities: list[str]
    actions: list[dict[str, Any]]


class AgentActionInfo(BaseModel):
    """Information about an agent action."""

    name: str
    description: str
    parameters: dict[str, Any]
    required_capabilities: list[str]


class ExecuteRequest(BaseModel):
    """Request to execute an agent action."""

    parameters: dict[str, Any] = Field(default_factory=dict)
    repository_id: uuid.UUID | None = None


class ExecuteResponse(BaseModel):
    """Response from agent execution."""

    success: bool
    agent_name: str
    action: str
    data: Any | None = None
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    suggested_next_agent: str | None = None
    suggested_next_action: str | None = None


class AgentHealthResponse(BaseModel):
    """Health check response for all agents."""

    agents: dict[str, bool]
    all_healthy: bool


# =============================================================================
# Routes
# =============================================================================


@router.get("", response_model=list[AgentInfo])
async def list_agents() -> list[AgentInfo]:
    """List all registered agents."""
    agents = agent_registry.list_agents()
    return [
        AgentInfo(
            name=agent.name,
            description=agent.description,
            version=agent.version,
            capabilities=[cap.value for cap in agent.capabilities],
            actions=[
                {
                    "name": action.name,
                    "description": action.description,
                }
                for action in agent.actions
            ],
        )
        for agent in agents
    ]


@router.get("/health", response_model=AgentHealthResponse)
async def health_check() -> AgentHealthResponse:
    """Run health checks on all agents."""
    results = await agent_registry.health_check_all()
    return AgentHealthResponse(
        agents=results,
        all_healthy=all(results.values()) if results else False,
    )


@router.get("/capabilities")
async def list_capabilities() -> dict[str, list[str]]:
    """List all available capabilities and which agents provide them."""
    capabilities: dict[str, list[str]] = {}

    for cap in AgentCapability:
        agents = agent_registry.get_agents_by_capability(cap)
        if agents:
            capabilities[cap.value] = [agent.name for agent in agents]

    return {"capabilities": capabilities}


@router.get("/tools")
async def get_tool_definitions() -> dict[str, list[dict]]:
    """Get all tool definitions for LLM function calling."""
    return {"tools": agent_registry.get_all_tool_definitions()}


@router.get("/{agent_name}", response_model=AgentInfo)
async def get_agent(agent_name: str) -> AgentInfo:
    """Get information about a specific agent."""
    agent = agent_registry.get(agent_name)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_name}",
        )

    return AgentInfo(
        name=agent.name,
        description=agent.description,
        version=agent.version,
        capabilities=[cap.value for cap in agent.capabilities],
        actions=[
            {
                "name": action.name,
                "description": action.description,
            }
            for action in agent.actions
        ],
    )


@router.get("/{agent_name}/actions", response_model=list[AgentActionInfo])
async def get_agent_actions(agent_name: str) -> list[AgentActionInfo]:
    """Get all actions available for an agent."""
    agent = agent_registry.get(agent_name)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_name}",
        )

    return [
        AgentActionInfo(
            name=action.name,
            description=action.description,
            parameters=action.parameters,
            required_capabilities=[cap.value for cap in action.required_capabilities],
        )
        for action in agent.actions
    ]


@router.get("/{agent_name}/actions/{action_name}", response_model=AgentActionInfo)
async def get_action_details(agent_name: str, action_name: str) -> AgentActionInfo:
    """Get details about a specific action."""
    agent = agent_registry.get(agent_name)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_name}",
        )

    action = agent.get_action(action_name)
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action not found: {action_name}",
        )

    return AgentActionInfo(
        name=action.name,
        description=action.description,
        parameters=action.parameters,
        required_capabilities=[cap.value for cap in action.required_capabilities],
    )


@router.post("/{agent_name}/execute/{action_name}", response_model=ExecuteResponse)
async def execute_action(
    agent_name: str,
    action_name: str,
    request: ExecuteRequest,
    current_user: CurrentUser,
    db: DbSession,
    http_request: Request,
) -> ExecuteResponse:
    """Execute an action on an agent."""
    logger.info(f"[AGENT] Starting {agent_name}:{action_name}")
    logger.info(f"[AGENT] Parameters: {request.parameters}")
    start_time = time.time()

    agent = agent_registry.get(agent_name)
    if not agent:
        logger.error(f"[AGENT] Agent not found: {agent_name}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_name}",
        )

    action = agent.get_action(action_name)
    if not action:
        logger.error(f"[AGENT] Action not found: {action_name}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action not found: {action_name}",
        )

    # Build context
    context = AgentContext(
        user_id=current_user.id,
        session_id=str(uuid.uuid4()),
    )

    # If repository_id is provided, get the repository path
    if request.repository_id:
        logger.info(f"[AGENT] Loading repository: {request.repository_id}")
        repo_service = RepositoryService(db)
        repo = await repo_service.get_by_id(request.repository_id)

        if not repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found",
            )
        if repo.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized",
            )
        if not repo.local_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Repository not cloned",
            )

        context.repository_path = Path(repo.local_path)
        context.repository_id = request.repository_id
        logger.info(f"[AGENT] Repository path: {repo.local_path}")

        # Add repository_path to parameters if action expects it
        if "repository_path" in str(action.parameters):
            request.parameters["repository_path"] = repo.local_path

    # Execute the action
    logger.info(f"[AGENT] Executing {agent_name}:{action_name}...")
    result = await agent_registry.execute(
        agent_name,
        action_name,
        context,
        **request.parameters,
    )

    elapsed = time.time() - start_time
    if result.success:
        logger.info(f"[AGENT] Completed {agent_name}:{action_name} in {elapsed:.2f}s")
        if result.data:
            # Log summary of result
            data_summary = str(result.data)[:200] + "..." if len(str(result.data)) > 200 else str(result.data)
            logger.info(f"[AGENT] Result: {data_summary}")
    else:
        logger.error(f"[AGENT] Failed {agent_name}:{action_name} in {elapsed:.2f}s: {result.error}")

    # Log the action
    audit_service = AuditService(db)
    await audit_service.log_action(
        action=f"agent_execute:{agent_name}:{action_name}",
        entity_type="agent",
        entity_id=None,
        user_id=current_user.id,
        details={
            "agent": agent_name,
            "action": action_name,
            "parameters": request.parameters,
            "success": result.success,
            "error": result.error,
        },
        request=http_request,
    )

    return ExecuteResponse(
        success=result.success,
        agent_name=result.agent_name,
        action=result.action,
        data=result.data,
        error=result.error,
        warnings=result.warnings,
        suggested_next_agent=result.suggested_next_agent,
        suggested_next_action=result.suggested_next_action,
    )


@router.post("/execute-by-capability/{capability}", response_model=ExecuteResponse)
async def execute_by_capability(
    capability: str,
    action_name: str,
    request: ExecuteRequest,
    current_user: CurrentUser,
    db: DbSession,
    http_request: Request,
) -> ExecuteResponse:
    """Execute an action using the first agent that provides a capability."""
    try:
        cap = AgentCapability(capability)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown capability: {capability}",
        )

    agents = agent_registry.get_agents_by_capability(cap)
    if not agents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No agent provides capability: {capability}",
        )

    # Use the first available agent
    agent = agents[0]

    # Build context
    context = AgentContext(
        user_id=current_user.id,
        session_id=str(uuid.uuid4()),
    )

    # Handle repository if provided
    if request.repository_id:
        repo_service = RepositoryService(db)
        repo = await repo_service.get_by_id(request.repository_id)

        if repo and repo.owner_id == current_user.id and repo.local_path:
            context.repository_path = Path(repo.local_path)
            context.repository_id = request.repository_id
            request.parameters["repository_path"] = repo.local_path

    # Execute the action
    result = await agent_registry.execute(
        agent.name,
        action_name,
        context,
        **request.parameters,
    )

    # Log the action
    audit_service = AuditService(db)
    await audit_service.log_action(
        action=f"agent_execute_by_capability:{capability}:{action_name}",
        entity_type="agent",
        entity_id=None,
        user_id=current_user.id,
        details={
            "capability": capability,
            "selected_agent": agent.name,
            "action": action_name,
            "success": result.success,
        },
        request=http_request,
    )

    return ExecuteResponse(
        success=result.success,
        agent_name=result.agent_name,
        action=result.action,
        data=result.data,
        error=result.error,
        warnings=result.warnings,
        suggested_next_agent=result.suggested_next_agent,
        suggested_next_action=result.suggested_next_action,
    )
