"""Analysis Agent for JDK upgrade impact assessment.

This agent handles impact analysis WITH LLM explanations.
For fixing and patching, use separate agents:
- FixerAgent: generate code fixes
- PatcherAgent: create patches
"""

import asyncio
import logging
from pathlib import Path

from app.agents.base import Agent, AgentAction, AgentCapability, AgentContext, AgentResult
from app.agents.registry import register_agent
from app.services.analyzer_service import analyzer_service
from app.services.llm_service import llm_service
from app.services.release_notes_service import release_notes_service

logger = logging.getLogger(__name__)


@register_agent
class AnalysisAgent(Agent):
    """Agent for analyzing JDK upgrade impacts WITH LLM explanations.

    Capabilities:
    - Fetch and parse JDK release notes
    - Analyze code for deprecated/removed APIs
    - Calculate upgrade risk scores
    - LLM-powered impact explanations

    For code modifications, use separate agents:
    - fixer: generate code fixes
    - patcher: create patches
    """

    name = "analysis"
    description = "JDK upgrade impact analysis with LLM explanations"
    version = "2.0.0"

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability.IMPACT_ANALYSIS,
            AgentCapability.SECURITY_SCANNING,
            AgentCapability.DEPENDENCY_ANALYSIS,
        ]

    @property
    def actions(self) -> list[AgentAction]:
        return [
            AgentAction(
                name="get_release_notes",
                description="Fetch release notes for changes between two JDK versions",
                parameters={
                    "type": "object",
                    "properties": {
                        "from_version": {
                            "type": "string",
                            "description": "Source JDK version (e.g., '11.0.18')",
                        },
                        "to_version": {
                            "type": "string",
                            "description": "Target JDK version (e.g., '11.0.22')",
                        },
                    },
                    "required": ["from_version", "to_version"],
                },
            ),
            AgentAction(
                name="analyze_impact",
                description="Analyze repository for JDK upgrade impacts with LLM explanations",
                parameters={
                    "type": "object",
                    "properties": {
                        "repository_path": {
                            "type": "string",
                            "description": "Path to the repository",
                        },
                        "from_version": {
                            "type": "string",
                            "description": "Current JDK version",
                        },
                        "to_version": {
                            "type": "string",
                            "description": "Target JDK version",
                        },
                        "llm_provider": {
                            "type": "string",
                            "description": "LLM provider for explanations (optional)",
                        },
                        "skip_llm": {
                            "type": "boolean",
                            "description": "Skip LLM explanations for faster results",
                            "default": False,
                        },
                    },
                    "required": ["repository_path", "from_version", "to_version"],
                },
                required_capabilities=[AgentCapability.IMPACT_ANALYSIS],
            ),
            AgentAction(
                name="get_security_advisories",
                description="Get security fixes between two JDK versions",
                parameters={
                    "type": "object",
                    "properties": {
                        "from_version": {
                            "type": "string",
                            "description": "Source JDK version",
                        },
                        "to_version": {
                            "type": "string",
                            "description": "Target JDK version",
                        },
                    },
                    "required": ["from_version", "to_version"],
                },
                required_capabilities=[AgentCapability.SECURITY_SCANNING],
            ),
            AgentAction(
                name="suggest_upgrade_path",
                description="Suggest the best upgrade path between JDK versions",
                parameters={
                    "type": "object",
                    "properties": {
                        "repository_path": {
                            "type": "string",
                            "description": "Path to the repository",
                        },
                        "target_version": {
                            "type": "string",
                            "description": "Desired target JDK version",
                        },
                    },
                    "required": ["repository_path", "target_version"],
                },
            ),
        ]

    async def execute(self, action: str, context: AgentContext, **kwargs) -> AgentResult:
        """Execute an analysis action."""
        try:
            if action == "get_release_notes":
                return await self._get_release_notes(context, **kwargs)
            elif action == "analyze_impact":
                return await self._analyze_impact(context, **kwargs)
            elif action == "get_security_advisories":
                return await self._get_security_advisories(context, **kwargs)
            elif action == "suggest_upgrade_path":
                return await self._suggest_upgrade_path(context, **kwargs)
            else:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    action=action,
                    error=f"Unknown action: {action}",
                )
        except Exception as e:
            logger.error(f"[AnalysisAgent] Action {action} failed: {e}")
            return AgentResult(
                success=False,
                agent_name=self.name,
                action=action,
                error=str(e),
            )

    async def _get_release_notes(self, context: AgentContext, **kwargs) -> AgentResult:
        """Fetch release notes between versions."""
        from_version = kwargs["from_version"]
        to_version = kwargs["to_version"]

        logger.info(f"[AnalysisAgent] Fetching release notes: {from_version} -> {to_version}")
        changes = await release_notes_service.get_changes_between_versions(
            from_version,
            to_version,
        )
        logger.info(f"[AnalysisAgent] Found {len(changes)} changes")

        if not changes:
            return AgentResult(
                success=True,
                agent_name=self.name,
                action="get_release_notes",
                data={
                    "from_version": from_version,
                    "to_version": to_version,
                    "changes": [],
                    "message": "No changes found between versions",
                },
            )

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="get_release_notes",
            data={
                "from_version": from_version,
                "to_version": to_version,
                "total_changes": len(changes),
                "changes": [
                    {
                        "version": c.version,
                        "type": c.change_type.value if hasattr(c.change_type, 'value') else str(c.change_type),
                        "component": c.component,
                        "description": c.description,
                        "affected_classes": c.affected_classes,
                        "affected_methods": c.affected_methods,
                        "cve_id": c.cve_id,
                        "migration_notes": c.migration_notes,
                    }
                    for c in changes
                ],
                "by_type": self._group_by_type(changes),
            },
        )

    async def _analyze_impact(self, context: AgentContext, **kwargs) -> AgentResult:
        """Analyze repository for JDK upgrade impacts with LLM explanations."""
        repo_path = Path(kwargs["repository_path"])
        from_version = kwargs["from_version"]
        to_version = kwargs["to_version"]
        llm_provider = kwargs.get("llm_provider")
        skip_llm = kwargs.get("skip_llm", False)

        logger.info(f"[AnalysisAgent] Analyzing impact: {repo_path}")
        logger.info(f"[AnalysisAgent] Version range: {from_version} -> {to_version}")

        result = await analyzer_service.analyze_repository(
            repo_path,
            from_version,
            to_version,
        )
        logger.info(f"[AnalysisAgent] Analysis complete: {len(result.impacts)} impacts, risk_score={result.risk_score}")

        if result.error_message:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="analyze_impact",
                error=result.error_message,
            )

        # Build impact data
        impacts_data = []
        for impact in result.impacts:
            impacts_data.append({
                "file_path": impact.location.file_path,
                "line_number": impact.location.line_number,
                "code_snippet": impact.location.code_snippet,
                "change_type": impact.change.change_type.value if hasattr(impact.change.change_type, 'value') else str(impact.change.change_type),
                "severity": impact.severity.value if hasattr(impact.severity, 'value') else str(impact.severity),
                "description": impact.change.description,
                "affected_class": impact.affected_class,
                "affected_method": impact.affected_method,
                "cve_id": impact.change.cve_id,
                "suggested_fix": impact.suggested_fix,
            })

        # Add LLM explanations if available and not skipped
        if impacts_data and not skip_llm and llm_service.available_providers:
            logger.info(f"[AnalysisAgent] Adding LLM explanations for {len(impacts_data)} impacts (parallel)")
            impacts_data = await self._add_llm_explanations(impacts_data, llm_provider)

        # Suggest next agent based on results
        suggested_next = None
        suggested_action = None

        if impacts_data:
            # Has impacts - suggest fixing
            suggested_next = "fixer"
            suggested_action = "generate_fixes"
        elif result.risk_score == 0:
            # No impacts - suggest version bump
            suggested_next = "renovate"
            suggested_action = "preview_version_bump"

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="analyze_impact",
            data={
                "from_version": from_version,
                "to_version": to_version,
                "risk_score": result.risk_score,
                "risk_level": result.risk_level.value if hasattr(result.risk_level, 'value') else str(result.risk_level),
                "total_files_analyzed": result.total_files_analyzed,
                "total_impacts": len(result.impacts),
                "impacts": impacts_data,
                "summary": result.summary,
                "suggestions": result.suggestions,
            },
            warnings=self._generate_warnings(result),
            suggested_next_agent=suggested_next,
            suggested_next_action=suggested_action,
        )

    async def _add_llm_explanations(self, impacts: list[dict], llm_provider: str | None) -> list[dict]:
        """Add LLM explanations to impacts in parallel."""
        max_concurrent = 10
        semaphore = asyncio.Semaphore(max_concurrent)

        async def explain_one(impact: dict, index: int) -> dict:
            async with semaphore:
                logger.info(f"[AnalysisAgent] Explaining impact {index+1}/{len(impacts)}")
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
                    logger.warning(f"[AnalysisAgent] Failed to explain impact: {e}")
                    return {**impact, "llm_explanation": {"error": str(e)}}

        tasks = [explain_one(impact, i) for i, impact in enumerate(impacts)]
        return await asyncio.gather(*tasks)

    async def _get_security_advisories(self, context: AgentContext, **kwargs) -> AgentResult:
        """Get security-related changes between versions."""
        from_version = kwargs["from_version"]
        to_version = kwargs["to_version"]

        changes = await release_notes_service.get_changes_between_versions(
            from_version,
            to_version,
        )

        # Filter to security changes only
        from app.models.analysis import ChangeType
        security_changes = [c for c in changes if c.change_type == ChangeType.SECURITY]

        cves = [c.cve_id for c in security_changes if c.cve_id]

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="get_security_advisories",
            data={
                "from_version": from_version,
                "to_version": to_version,
                "total_security_fixes": len(security_changes),
                "cves": cves,
                "advisories": [
                    {
                        "version": c.version,
                        "cve_id": c.cve_id,
                        "component": c.component,
                        "description": c.description,
                        "affected_classes": c.affected_classes,
                    }
                    for c in security_changes
                ],
            },
            warnings=["Upgrade recommended for security fixes"] if cves else [],
        )

    async def _suggest_upgrade_path(self, context: AgentContext, **kwargs) -> AgentResult:
        """Suggest the best upgrade path."""
        repo_path = Path(kwargs["repository_path"])
        target_version = kwargs["target_version"]

        # First detect current version using renovate agent
        from app.services.renovate_service import renovate_service

        current = await renovate_service.detect_jdk_version(repo_path)
        if not current:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="suggest_upgrade_path",
                error="Could not detect current JDK version",
                suggested_next_agent="renovate",
                suggested_next_action="detect_version",
            )

        # Parse target version
        target_parts = self._parse_version(target_version)
        if not target_parts:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="suggest_upgrade_path",
                error=f"Invalid target version format: {target_version}",
            )

        # Build upgrade path
        steps = []

        if current.major == target_parts[0]:
            # Same major version - patch upgrade
            steps.append({
                "type": "patch",
                "from_version": current.full,
                "to_version": target_version,
                "agent": "renovate",
                "actions": ["preview_version_bump", "apply_version_bump"],
                "risk": "low",
                "description": f"Patch upgrade from {current.full} to {target_version}",
            })
        else:
            # Major version upgrade - need OpenRewrite
            lts_versions = [8, 11, 17, 21]
            current_major = current.major
            target_major = target_parts[0]

            # Build incremental upgrade path through LTS versions
            for lts in lts_versions:
                if current_major < lts <= target_major:
                    steps.append({
                        "type": "major",
                        "from_version": str(current_major),
                        "to_version": str(lts),
                        "agent": "openrewrite",
                        "actions": ["analyze_migration", "run_recipe"],
                        "risk": "high",
                        "description": f"Major upgrade from JDK {current_major} to JDK {lts}",
                    })
                    current_major = lts

            # Final patch if needed
            if target_version != str(target_major):
                steps.append({
                    "type": "patch",
                    "from_version": f"{target_major}.0.0",
                    "to_version": target_version,
                    "agent": "renovate",
                    "actions": ["preview_version_bump", "apply_version_bump"],
                    "risk": "low",
                    "description": f"Final patch to {target_version}",
                })

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="suggest_upgrade_path",
            data={
                "current_version": current.full,
                "target_version": target_version,
                "total_steps": len(steps),
                "steps": steps,
                "recommendation": self._generate_recommendation(steps),
            },
        )

    @staticmethod
    def _group_by_type(changes) -> dict[str, int]:
        """Group changes by type."""
        groups: dict[str, int] = {}
        for change in changes:
            type_str = change.change_type.value if hasattr(change.change_type, 'value') else str(change.change_type)
            groups[type_str] = groups.get(type_str, 0) + 1
        return groups

    @staticmethod
    def _generate_warnings(result) -> list[str]:
        """Generate warnings based on analysis result."""
        from app.models.analysis import RiskLevel

        warnings = []

        if result.risk_level == RiskLevel.CRITICAL:
            warnings.append("CRITICAL: This upgrade will likely break the build")
        elif result.risk_level == RiskLevel.HIGH:
            warnings.append("HIGH: Significant changes required before upgrade")

        # Count by severity
        critical_count = sum(
            1 for i in result.impacts
            if i.severity == RiskLevel.CRITICAL
        )
        if critical_count > 0:
            warnings.append(f"{critical_count} critical issues must be resolved")

        return warnings

    @staticmethod
    def _generate_recommendation(steps) -> str:
        """Generate recommendation based on upgrade steps."""
        if not steps:
            return "No upgrade needed"

        if len(steps) == 1 and steps[0]["type"] == "patch":
            return "Simple patch upgrade. Low risk, can be automated."

        major_steps = [s for s in steps if s["type"] == "major"]
        if major_steps:
            return (
                f"Multi-step upgrade required. {len(major_steps)} major version jump(s). "
                "Run impact analysis before each step. "
                "Consider using OpenRewrite recipes for automated migration."
            )

        return "Proceed with caution. Review changes before applying."

    @staticmethod
    def _parse_version(version: str) -> tuple[int, int, int] | None:
        """Parse version string."""
        import re
        match = re.match(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", version)
        if match:
            return (
                int(match.group(1)),
                int(match.group(2) or 0),
                int(match.group(3) or 0),
            )
        return None

    async def health_check(self) -> bool:
        """Check if analysis agent is healthy."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get("https://api.adoptium.net/v3/info/available_releases")
                return resp.status_code == 200
        except Exception:
            return False
