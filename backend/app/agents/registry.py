"""Agent registry for managing multiple agents."""

from typing import Type

from app.agents.base import Agent, AgentCapability, AgentContext, AgentResult


class AgentRegistry:
    """Registry for managing and discovering agents.

    Agents can be registered using the @register_agent decorator
    or explicitly via registry.register().
    """

    def __init__(self):
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        """Register an agent instance."""
        if agent.name in self._agents:
            raise ValueError(f"Agent already registered: {agent.name}")
        self._agents[agent.name] = agent

    def unregister(self, name: str) -> None:
        """Unregister an agent by name."""
        if name in self._agents:
            del self._agents[name]

    def get(self, name: str) -> Agent | None:
        """Get an agent by name."""
        return self._agents.get(name)

    def list_agents(self) -> list[Agent]:
        """List all registered agents."""
        return list(self._agents.values())

    def get_agents_by_capability(self, capability: AgentCapability) -> list[Agent]:
        """Get all agents that provide a specific capability."""
        return [agent for agent in self._agents.values() if agent.can_handle(capability)]

    async def execute(
        self,
        agent_name: str,
        action: str,
        context: AgentContext,
        **kwargs,
    ) -> AgentResult:
        """Execute an action on a specific agent."""
        agent = self.get(agent_name)
        if not agent:
            return AgentResult(
                success=False,
                agent_name=agent_name,
                action=action,
                error=f"Agent not found: {agent_name}",
            )

        action_def = agent.get_action(action)
        if not action_def:
            return AgentResult(
                success=False,
                agent_name=agent_name,
                action=action,
                error=f"Action not found: {action}",
            )

        try:
            return await agent.execute(action, context, **kwargs)
        except Exception as e:
            return AgentResult(
                success=False,
                agent_name=agent_name,
                action=action,
                error=str(e),
            )

    async def execute_by_capability(
        self,
        capability: AgentCapability,
        action: str,
        context: AgentContext,
        **kwargs,
    ) -> AgentResult:
        """Execute an action on the first agent that provides a capability."""
        agents = self.get_agents_by_capability(capability)
        if not agents:
            return AgentResult(
                success=False,
                agent_name="unknown",
                action=action,
                error=f"No agent found for capability: {capability}",
            )

        # Use the first available agent
        return await self.execute(agents[0].name, action, context, **kwargs)

    def get_all_tool_definitions(self) -> list[dict]:
        """Get tool definitions from all agents for LLM function calling."""
        tools = []
        for agent in self._agents.values():
            for tool_def in agent.get_tool_definitions():
                # Prefix tool name with agent name to avoid conflicts
                tool_def = tool_def.copy()
                tool_def["function"] = tool_def["function"].copy()
                tool_def["function"]["name"] = f"{agent.name}:{tool_def['function']['name']}"
                tools.append(tool_def)
        return tools

    async def health_check_all(self) -> dict[str, bool]:
        """Run health checks on all agents."""
        results = {}
        for name, agent in self._agents.items():
            try:
                results[name] = await agent.health_check()
            except Exception:
                results[name] = False
        return results


# Global registry instance
agent_registry = AgentRegistry()


def register_agent(agent_class: Type[Agent]) -> Type[Agent]:
    """Decorator to register an agent class.

    Usage:
        @register_agent
        class MyAgent(Agent):
            name = "my_agent"
            ...
    """
    agent_instance = agent_class()
    agent_registry.register(agent_instance)
    return agent_class
