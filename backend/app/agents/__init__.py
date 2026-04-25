"""Multi-agent system for Java patching automation."""

from app.agents.base import Agent, AgentCapability, AgentContext, AgentResult, AgentStatus
from app.agents.registry import agent_registry, register_agent

# Import agents to trigger registration
from app.agents import openrewrite_agent, renovate_agent  # noqa: F401

__all__ = [
    "Agent",
    "AgentCapability",
    "AgentContext",
    "AgentResult",
    "AgentStatus",
    "agent_registry",
    "register_agent",
]
