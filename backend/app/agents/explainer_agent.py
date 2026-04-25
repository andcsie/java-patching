"""Explainer Agent - Uses LLM to explain code impacts."""

import logging

from app.agents.base import Agent, AgentAction, AgentCapability, AgentContext, AgentResult
from app.agents.bus import AgentMessage, MessageType, agent_bus
from app.agents.registry import register_agent
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


@register_agent
class ExplainerAgent(Agent):
    """Agent for LLM-powered impact explanations.

    Capabilities:
    - Explain why code is affected by JDK changes
    - Describe runtime behavior implications
    - Provide security context for CVE-related changes
    - Generate human-readable summaries

    Uses the LLM service for natural language generation.
    Communicates results via AgentBus.
    """

    name = "explainer"
    description = "LLM-powered code impact explanations"
    version = "1.0.0"

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability.IMPACT_ANALYSIS,
        ]

    @property
    def actions(self) -> list[AgentAction]:
        return [
            AgentAction(
                name="explain",
                description="Explain each impact in detail using LLM",
                parameters={
                    "type": "object",
                    "properties": {
                        "impacts": {
                            "type": "array",
                            "description": "List of impacts from impact analysis",
                        },
                        "llm_provider": {
                            "type": "string",
                            "description": "LLM provider to use (optional)",
                        },
                    },
                    "required": ["impacts"],
                },
            ),
            AgentAction(
                name="explain_single",
                description="Explain a single impact in detail",
                parameters={
                    "type": "object",
                    "properties": {
                        "code_snippet": {
                            "type": "string",
                            "description": "The affected code",
                        },
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file",
                        },
                        "line_number": {
                            "type": "integer",
                            "description": "Line number of the impact",
                        },
                        "change_description": {
                            "type": "string",
                            "description": "Description of the JDK change",
                        },
                        "change_type": {
                            "type": "string",
                            "description": "Type of change (deprecated, removed, etc.)",
                        },
                        "cve_id": {
                            "type": "string",
                            "description": "CVE ID if security-related",
                        },
                        "llm_provider": {
                            "type": "string",
                            "description": "LLM provider to use",
                        },
                    },
                    "required": ["code_snippet", "change_description", "change_type"],
                },
            ),
            AgentAction(
                name="generate_summary",
                description="Generate a summary of all impacts",
                parameters={
                    "type": "object",
                    "properties": {
                        "impacts": {
                            "type": "array",
                            "description": "List of impacts",
                        },
                        "llm_provider": {
                            "type": "string",
                            "description": "LLM provider to use",
                        },
                    },
                    "required": ["impacts"],
                },
            ),
        ]

    async def execute(self, action: str, context: AgentContext, **kwargs) -> AgentResult:
        """Execute an explanation action."""
        try:
            if action == "explain":
                return await self._explain(context, **kwargs)
            elif action == "explain_single":
                return await self._explain_single(context, **kwargs)
            elif action == "generate_summary":
                return await self._generate_summary(context, **kwargs)
            else:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    action=action,
                    error=f"Unknown action: {action}",
                )
        except Exception as e:
            logger.error(f"[Explainer] Action {action} failed: {e}")
            return AgentResult(
                success=False,
                agent_name=self.name,
                action=action,
                error=str(e),
            )

    async def _explain(self, context: AgentContext, **kwargs) -> AgentResult:
        """Explain all impacts using LLM."""
        import asyncio

        impacts = kwargs.get("impacts", [])
        llm_provider = kwargs.get("llm_provider")
        max_concurrent = kwargs.get("max_concurrent", 10)  # Parallel LLM calls

        if not impacts:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="explain",
                error="No impacts provided. Run impact analysis first.",
            )

        if not llm_service.available_providers:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="explain",
                error="No LLM providers configured. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY.",
            )

        logger.info(f"[Explainer] Explaining {len(impacts)} impacts (parallel, max {max_concurrent})")

        # Process impacts in parallel batches
        semaphore = asyncio.Semaphore(max_concurrent)

        async def explain_one(impact: dict, index: int) -> dict:
            async with semaphore:
                logger.info(f"[Explainer] Explaining impact {index+1}/{len(impacts)}")
                try:
                    explanation = await llm_service.explain_impact(
                        code_snippet=impact.get("code_snippet", ""),
                        file_path=impact.get("file_path", ""),
                        line_number=impact.get("line_number", 0),
                        change_description=impact.get("description", ""),
                        change_type=impact.get("change_type", ""),
                        cve_id=impact.get("cve_id"),
                        provider=llm_provider,
                    )
                    return {**impact, "llm_explanation": explanation}
                except Exception as e:
                    logger.warning(f"[Explainer] Failed to explain impact: {e}")
                    return {**impact, "llm_explanation": {"error": str(e)}}

        # Run all explanations in parallel (with semaphore limiting concurrency)
        tasks = [explain_one(impact, i) for i, impact in enumerate(impacts)]
        explained_impacts = await asyncio.gather(*tasks)

        logger.info(f"[Explainer] Explained {len(explained_impacts)} impacts")

        result_data = {
            "total_explained": len(explained_impacts),
            "explained_impacts": explained_impacts,
        }

        # Publish completion event
        await agent_bus.publish(
            AgentMessage(
                type=MessageType.EVENT,
                from_agent=self.name,
                action="complete",
                payload=result_data,
            )
        )

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="explain",
            data=result_data,
            suggested_next_agent="fixer",
            suggested_next_action="generate_fixes",
        )

    async def _explain_single(self, context: AgentContext, **kwargs) -> AgentResult:
        """Explain a single impact."""
        llm_provider = kwargs.get("llm_provider")

        if not llm_service.available_providers:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="explain_single",
                error="No LLM providers configured.",
            )

        try:
            explanation = await llm_service.explain_impact(
                code_snippet=kwargs.get("code_snippet", ""),
                file_path=kwargs.get("file_path", ""),
                line_number=kwargs.get("line_number", 0),
                change_description=kwargs.get("change_description", ""),
                change_type=kwargs.get("change_type", ""),
                cve_id=kwargs.get("cve_id"),
                provider=llm_provider,
            )

            return AgentResult(
                success=True,
                agent_name=self.name,
                action="explain_single",
                data=explanation,
            )
        except Exception as e:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="explain_single",
                error=str(e),
            )

    async def _generate_summary(self, context: AgentContext, **kwargs) -> AgentResult:
        """Generate a summary of all impacts."""
        impacts = kwargs.get("impacts", [])
        llm_provider = kwargs.get("llm_provider")

        if not impacts:
            return AgentResult(
                success=True,
                agent_name=self.name,
                action="generate_summary",
                data={
                    "summary": "No impacts found - code is compatible with the target JDK version.",
                },
            )

        if not llm_service.available_providers:
            # Generate a basic summary without LLM
            by_type: dict[str, int] = {}
            for impact in impacts:
                t = impact.get("change_type", "unknown")
                by_type[t] = by_type.get(t, 0) + 1

            summary_parts = []
            for change_type, count in by_type.items():
                summary_parts.append(f"{count} {change_type} issue(s)")

            return AgentResult(
                success=True,
                agent_name=self.name,
                action="generate_summary",
                data={
                    "summary": f"Found {len(impacts)} total impacts: " + ", ".join(summary_parts),
                    "by_type": by_type,
                },
            )

        # Use LLM to generate summary
        provider = llm_provider or llm_service.default_provider

        impact_descriptions = []
        for impact in impacts[:10]:  # Limit to first 10 for summary
            impact_descriptions.append(
                f"- {impact.get('file_path', 'unknown')}:{impact.get('line_number', 0)}: "
                f"{impact.get('change_type', 'unknown')} - {impact.get('description', 'No description')}"
            )

        prompt = f"""Summarize the following JDK upgrade impacts in 2-3 sentences.
Focus on the most critical issues and overall risk:

{chr(10).join(impact_descriptions)}

Total impacts: {len(impacts)}
"""

        try:
            response = await llm_service.complete(
                messages=[{"role": "user", "content": prompt}],
                provider=provider,
                max_tokens=500,
            )

            return AgentResult(
                success=True,
                agent_name=self.name,
                action="generate_summary",
                data={
                    "summary": response,
                    "total_impacts": len(impacts),
                },
            )
        except Exception as e:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="generate_summary",
                error=str(e),
            )

    async def health_check(self) -> bool:
        """Check if explainer agent is healthy."""
        return bool(llm_service.available_providers)
