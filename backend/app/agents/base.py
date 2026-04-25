"""Base classes for the multi-agent system."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any
import uuid


class AgentStatus(StrEnum):
    """Agent execution status."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentCapability(StrEnum):
    """Capabilities that agents can provide."""

    # Version management
    VERSION_DETECTION = "version_detection"
    PATCH_DISCOVERY = "patch_discovery"
    VERSION_BUMPING = "version_bumping"

    # Code transformation
    CODE_MIGRATION = "code_migration"
    RECIPE_EXECUTION = "recipe_execution"
    REFACTORING = "refactoring"

    # Analysis
    IMPACT_ANALYSIS = "impact_analysis"
    SECURITY_SCANNING = "security_scanning"
    DEPENDENCY_ANALYSIS = "dependency_analysis"

    # Configuration
    CONFIG_GENERATION = "config_generation"
    BUILD_TOOL_SUPPORT = "build_tool_support"


@dataclass
class AgentContext:
    """Context for agent execution."""

    user_id: uuid.UUID
    repository_path: Path | None = None
    repository_id: uuid.UUID | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Execution state
    current_task: str | None = None
    progress: float = 0.0  # 0.0 to 1.0
    status: AgentStatus = AgentStatus.IDLE


@dataclass
class AgentResult:
    """Result from agent execution."""

    success: bool
    agent_name: str
    action: str
    data: Any = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # For chaining to other agents
    suggested_next_agent: str | None = None
    suggested_next_action: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "agent_name": self.agent_name,
            "action": self.action,
            "data": self.data,
            "error": self.error,
            "warnings": self.warnings,
            "metadata": self.metadata,
            "suggested_next_agent": self.suggested_next_agent,
            "suggested_next_action": self.suggested_next_action,
        }


@dataclass
class AgentAction:
    """Definition of an action an agent can perform."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    required_capabilities: list[AgentCapability] = field(default_factory=list)

    def to_tool_definition(self) -> dict:
        """Convert to LLM function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class Agent(ABC):
    """Base class for all agents in the system.

    An agent is a self-contained unit that provides specific capabilities
    for Java patching, version management, or code transformation.

    Examples: RenovateAgent, OpenRewriteAgent, AnalysisAgent
    """

    # Agent metadata (override in subclasses)
    name: str = "base_agent"
    description: str = "Base agent"
    version: str = "1.0.0"

    @property
    @abstractmethod
    def capabilities(self) -> list[AgentCapability]:
        """List of capabilities this agent provides."""
        ...

    @property
    @abstractmethod
    def actions(self) -> list[AgentAction]:
        """List of actions this agent can perform."""
        ...

    @abstractmethod
    async def execute(self, action: str, context: AgentContext, **kwargs) -> AgentResult:
        """Execute an action with the given parameters."""
        ...

    async def health_check(self) -> bool:
        """Check if the agent is healthy and ready to execute."""
        return True

    def can_handle(self, capability: AgentCapability) -> bool:
        """Check if this agent provides a specific capability."""
        return capability in self.capabilities

    def get_action(self, name: str) -> AgentAction | None:
        """Get an action by name."""
        for action in self.actions:
            if action.name == name:
                return action
        return None

    def get_tool_definitions(self) -> list[dict]:
        """Get all actions as LLM tool definitions."""
        return [action.to_tool_definition() for action in self.actions]
