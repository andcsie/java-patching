"""Multi-agent system for Java patching automation.

Architecture:
- AgentBus: Central message bus for inter-agent communication
- WorkflowContext: Shared state (blackboard pattern) for workflow execution
- Specialized Agents: Single-responsibility agents that communicate via the bus

Agent Pipeline:
1. OrchestratorAgent - Coordinates workflows
2. ScannerAgent - Scans repository for Java files
3. ReleaseNotesAgent - Fetches JDK release notes
4. ImpactAgent - Analyzes code impacts
5. ExplainerAgent - LLM-powered explanations
6. FixerAgent - LLM-powered fix generation
7. PatcherAgent - Creates unified diff patches
8. RenovateAgent - Version bumping (patch upgrades)
9. OpenRewriteAgent - Recipe-based transformations (major upgrades)
"""

from app.agents.base import Agent, AgentCapability, AgentContext, AgentResult, AgentStatus
from app.agents.bus import AgentBus, AgentMessage, MessageType, WorkflowContext, agent_bus
from app.agents.registry import agent_registry, register_agent

# Import agents to trigger registration (order matters for dependencies)
from app.agents import (  # noqa: F401
    # Core analysis agents
    analysis_agent,
    # Specialized pipeline agents
    scanner_agent,
    release_notes_agent,
    impact_agent,
    explainer_agent,
    fixer_agent,
    patcher_agent,
    # Tool agents
    renovate_agent,
    openrewrite_agent,
    # Orchestration
    orchestrator_agent,
)

__all__ = [
    # Base classes
    "Agent",
    "AgentCapability",
    "AgentContext",
    "AgentResult",
    "AgentStatus",
    # Registry
    "agent_registry",
    "register_agent",
    # Bus communication
    "AgentBus",
    "AgentMessage",
    "MessageType",
    "WorkflowContext",
    "agent_bus",
]
