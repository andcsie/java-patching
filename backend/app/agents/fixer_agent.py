"""Fixer Agent - Uses LLM to generate code fixes for impacts."""

import logging
from pathlib import Path

from app.agents.base import Agent, AgentAction, AgentCapability, AgentContext, AgentResult
from app.agents.bus import AgentMessage, MessageType, agent_bus
from app.agents.registry import register_agent
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


@register_agent
class FixerAgent(Agent):
    """Agent for LLM-powered code fix generation.

    Capabilities:
    - Generate fixes for deprecated API usage
    - Suggest alternative implementations
    - Create migration code snippets
    - Handle security vulnerability fixes

    Uses the LLM service for code generation.
    Communicates results via AgentBus.
    """

    name = "fixer"
    description = "LLM-powered code fix generation"
    version = "1.0.0"

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability.CODE_MIGRATION,
            AgentCapability.REFACTORING,
        ]

    @property
    def actions(self) -> list[AgentAction]:
        return [
            AgentAction(
                name="generate_fixes",
                description="Generate fixes for all impacts using LLM",
                parameters={
                    "type": "object",
                    "properties": {
                        "impacts": {
                            "type": "array",
                            "description": "List of impacts to fix",
                        },
                        "llm_provider": {
                            "type": "string",
                            "description": "LLM provider to use (optional)",
                        },
                    },
                    "required": ["impacts"],
                },
                required_capabilities=[AgentCapability.CODE_MIGRATION],
            ),
            AgentAction(
                name="fix_single",
                description="Generate a fix for a single impact",
                parameters={
                    "type": "object",
                    "properties": {
                        "code_snippet": {
                            "type": "string",
                            "description": "The code to fix",
                        },
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file",
                        },
                        "change_description": {
                            "type": "string",
                            "description": "Description of the JDK change",
                        },
                        "change_type": {
                            "type": "string",
                            "description": "Type of change",
                        },
                        "full_file_content": {
                            "type": "string",
                            "description": "Full file content for context",
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
                name="validate_fix",
                description="Validate a generated fix",
                parameters={
                    "type": "object",
                    "properties": {
                        "original_code": {
                            "type": "string",
                            "description": "Original code",
                        },
                        "fixed_code": {
                            "type": "string",
                            "description": "Fixed code",
                        },
                        "change_type": {
                            "type": "string",
                            "description": "Type of change",
                        },
                    },
                    "required": ["original_code", "fixed_code", "change_type"],
                },
            ),
        ]

    async def execute(self, action: str, context: AgentContext, **kwargs) -> AgentResult:
        """Execute a fix generation action."""
        try:
            if action == "generate_fixes":
                return await self._generate_fixes(context, **kwargs)
            elif action == "fix_single":
                return await self._fix_single(context, **kwargs)
            elif action == "validate_fix":
                return await self._validate_fix(context, **kwargs)
            else:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    action=action,
                    error=f"Unknown action: {action}",
                )
        except Exception as e:
            logger.error(f"[Fixer] Action {action} failed: {e}")
            return AgentResult(
                success=False,
                agent_name=self.name,
                action=action,
                error=str(e),
            )

    async def _generate_fixes(self, context: AgentContext, **kwargs) -> AgentResult:
        """Generate fixes for all impacts."""
        impacts = kwargs.get("impacts", [])
        llm_provider = kwargs.get("llm_provider")

        if not impacts:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="generate_fixes",
                error="No impacts provided. Run impact analysis first.",
            )

        if not llm_service.available_providers:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="generate_fixes",
                error="No LLM providers configured.",
            )

        logger.info(f"[Fixer] Generating fixes for {len(impacts)} impacts")
        impacts_with_fixes = []

        for i, impact in enumerate(impacts):
            logger.info(f"[Fixer] Generating fix {i+1}/{len(impacts)}")
            try:
                # Read full file content for context
                file_path = impact.get("file_path", "")
                full_content = None
                if file_path:
                    try:
                        full_content = Path(file_path).read_text()
                    except Exception:
                        pass

                fix = await llm_service.generate_fix(
                    code_snippet=impact.get("code_snippet", ""),
                    file_path=file_path,
                    change_description=impact.get("description", ""),
                    change_type=impact.get("change_type", ""),
                    full_file_content=full_content,
                    provider=llm_provider,
                )

                impacts_with_fixes.append({
                    **impact,
                    "fix": fix,
                })
            except Exception as e:
                logger.warning(f"[Fixer] Failed to generate fix: {e}")
                impacts_with_fixes.append({
                    **impact,
                    "fix": {"error": str(e)},
                })

        logger.info(f"[Fixer] Generated {len(impacts_with_fixes)} fixes")

        # Count successful fixes
        successful_fixes = sum(
            1 for i in impacts_with_fixes
            if i.get("fix") and not i["fix"].get("error")
        )

        result_data = {
            "total_fixes": len(impacts_with_fixes),
            "successful_fixes": successful_fixes,
            "impacts_with_fixes": impacts_with_fixes,
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
            action="generate_fixes",
            data=result_data,
            suggested_next_agent="patcher",
            suggested_next_action="create_patches",
        )

    async def _fix_single(self, context: AgentContext, **kwargs) -> AgentResult:
        """Generate a fix for a single impact."""
        llm_provider = kwargs.get("llm_provider")

        if not llm_service.available_providers:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="fix_single",
                error="No LLM providers configured.",
            )

        try:
            fix = await llm_service.generate_fix(
                code_snippet=kwargs.get("code_snippet", ""),
                file_path=kwargs.get("file_path", ""),
                change_description=kwargs.get("change_description", ""),
                change_type=kwargs.get("change_type", ""),
                full_file_content=kwargs.get("full_file_content"),
                provider=llm_provider,
            )

            return AgentResult(
                success=True,
                agent_name=self.name,
                action="fix_single",
                data=fix,
            )
        except Exception as e:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="fix_single",
                error=str(e),
            )

    async def _validate_fix(self, context: AgentContext, **kwargs) -> AgentResult:
        """Validate a generated fix."""
        original_code = kwargs.get("original_code", "")
        fixed_code = kwargs.get("fixed_code", "")
        change_type = kwargs.get("change_type", "")

        issues = []
        warnings = []

        # Basic validation checks
        if not fixed_code:
            issues.append("Fixed code is empty")

        if original_code == fixed_code:
            warnings.append("Fixed code is identical to original")

        # Check for common issues
        if "TODO" in fixed_code or "FIXME" in fixed_code:
            warnings.append("Fix contains TODO/FIXME markers")

        if "..." in fixed_code or "// ..." in fixed_code:
            issues.append("Fix contains placeholder ellipsis")

        # Check if deprecated API is still present (basic check)
        if change_type == "deprecated":
            # Would need more sophisticated parsing here
            pass

        is_valid = len(issues) == 0

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="validate_fix",
            data={
                "valid": is_valid,
                "issues": issues,
                "warnings": warnings,
            },
        )

    async def health_check(self) -> bool:
        """Check if fixer agent is healthy."""
        return bool(llm_service.available_providers)
