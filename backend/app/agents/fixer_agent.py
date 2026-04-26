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
        """Generate fixes for impacts with optional chunking."""
        import asyncio

        impacts = kwargs.get("impacts", [])
        llm_provider = kwargs.get("llm_provider")
        max_concurrent = kwargs.get("max_concurrent", 10)  # Parallel LLM calls

        # Chunking support
        limit = kwargs.get("limit")  # Max impacts to process
        offset = kwargs.get("offset", 0)  # Starting index
        severity_filter = kwargs.get("severity")  # Filter by severity: high, medium, low

        if not impacts:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="generate_fixes",
                error="No impacts provided. Run impact analysis first.",
            )

        # Apply severity filter if specified
        if severity_filter:
            impacts = [i for i in impacts if i.get("severity") == severity_filter]
            logger.info(f"[Fixer] Filtered to {len(impacts)} impacts with severity={severity_filter}")

        total_impacts = len(impacts)

        # Apply offset and limit for chunking
        if offset > 0:
            impacts = impacts[offset:]
        if limit and limit > 0:
            impacts = impacts[:limit]

        if not impacts:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="generate_fixes",
                error=f"No impacts to process (offset={offset}, total={total_impacts})",
            )

        if not llm_service.available_providers:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="generate_fixes",
                error="No LLM providers configured.",
            )

        logger.info(f"[Fixer] Processing {len(impacts)} of {total_impacts} impacts (offset={offset}, limit={limit})")

        # Cache file contents to avoid re-reading
        file_cache: dict[str, str | None] = {}

        def get_file_content(file_path: str) -> str | None:
            if file_path not in file_cache:
                try:
                    file_cache[file_path] = Path(file_path).read_text()
                except Exception:
                    file_cache[file_path] = None
            return file_cache[file_path]

        semaphore = asyncio.Semaphore(max_concurrent)

        async def fix_one(impact: dict, index: int) -> dict:
            async with semaphore:
                code_snippet = impact.get("code_snippet", "").strip()

                # Skip import statements - they rarely need code fixes
                if code_snippet.startswith("import ") or code_snippet.startswith("package "):
                    logger.info(f"[Fixer] Skipping import/package statement {index+1}/{len(impacts)}")
                    return {**impact, "fix": {
                        "fixed_code": code_snippet,
                        "explanation": "Import/package statements typically don't need code changes",
                        "skipped": True,
                    }}

                logger.info(f"[Fixer] Generating fix {index+1}/{len(impacts)}")
                try:
                    file_path = impact.get("file_path", "")

                    fix = await llm_service.generate_fix(
                        code_snippet=code_snippet,
                        file_path=file_path,
                        change_description=impact.get("description", ""),
                        change_type=impact.get("change_type", ""),
                        full_file_content=None,  # Skip file content to reduce tokens
                        provider=llm_provider,
                    )
                    return {**impact, "fix": fix}
                except Exception as e:
                    logger.warning(f"[Fixer] Failed to generate fix: {e}")
                    return {**impact, "fix": {"error": str(e)}}

        # Run all fixes in parallel
        tasks = [fix_one(impact, i) for i, impact in enumerate(impacts)]
        impacts_with_fixes = await asyncio.gather(*tasks)

        logger.info(f"[Fixer] Generated {len(impacts_with_fixes)} fixes")

        # Count successful fixes
        successful_fixes = sum(
            1 for i in impacts_with_fixes
            if i.get("fix") and not i["fix"].get("error")
        )

        # Calculate if there are more impacts to process
        processed_end = offset + len(impacts_with_fixes)
        has_more = processed_end < total_impacts

        result_data = {
            "total_fixes": len(impacts_with_fixes),
            "successful_fixes": successful_fixes,
            "impacts_with_fixes": impacts_with_fixes,
            # Pagination info
            "pagination": {
                "offset": offset,
                "limit": limit,
                "processed": len(impacts_with_fixes),
                "total_available": total_impacts,
                "has_more": has_more,
                "next_offset": processed_end if has_more else None,
            },
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
