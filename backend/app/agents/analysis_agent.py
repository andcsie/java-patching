"""Analysis Agent for JDK upgrade impact assessment."""

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
    """Agent for analyzing JDK upgrade impacts.

    Capabilities:
    - Fetch and parse JDK release notes
    - Analyze code for deprecated/removed APIs
    - Calculate upgrade risk scores
    - Generate migration recommendations

    Best for: Understanding the impact before upgrading JDK versions
    """

    name = "analysis"
    description = "JDK upgrade impact analysis with release notes integration"
    version = "1.0.0"

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
                description="Analyze a repository for JDK upgrade impacts using release notes",
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
                            "description": "LLM provider for suggestions (optional)",
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
            AgentAction(
                name="explain_impacts",
                description="Use LLM to explain each impact in detail - why it's risky and what happens at runtime",
                parameters={
                    "type": "object",
                    "properties": {
                        "impacts": {
                            "type": "array",
                            "description": "List of impacts from analyze_impact",
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
                name="generate_fixes",
                description="Use LLM to generate code fixes for each impact",
                parameters={
                    "type": "object",
                    "properties": {
                        "impacts": {
                            "type": "array",
                            "description": "List of impacts from analyze_impact",
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
                name="create_patch",
                description="Generate unified diff patches for all fixes",
                parameters={
                    "type": "object",
                    "properties": {
                        "repository_path": {
                            "type": "string",
                            "description": "Path to the repository",
                        },
                        "impacts_with_fixes": {
                            "type": "array",
                            "description": "List of impacts with generated fixes",
                        },
                        "llm_provider": {
                            "type": "string",
                            "description": "LLM provider to use (optional)",
                        },
                    },
                    "required": ["repository_path", "impacts_with_fixes"],
                },
            ),
            AgentAction(
                name="full_analysis",
                description="Run complete analysis pipeline: analyze -> explain -> fix -> patch",
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
                            "description": "LLM provider to use (optional)",
                        },
                    },
                    "required": ["repository_path", "from_version", "to_version"],
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
            elif action == "explain_impacts":
                return await self._explain_impacts(context, **kwargs)
            elif action == "generate_fixes":
                return await self._generate_fixes(context, **kwargs)
            elif action == "create_patch":
                return await self._create_patch(context, **kwargs)
            elif action == "full_analysis":
                return await self._full_analysis(context, **kwargs)
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
        """Analyze repository for JDK upgrade impacts."""
        repo_path = Path(kwargs["repository_path"])
        from_version = kwargs["from_version"]
        to_version = kwargs["to_version"]
        llm_provider = kwargs.get("llm_provider")

        logger.info(f"[AnalysisAgent] Analyzing impact: {repo_path}")
        logger.info(f"[AnalysisAgent] Version range: {from_version} -> {to_version}")

        result = await analyzer_service.analyze_repository(
            repo_path,
            from_version,
            to_version,
            llm_provider,
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

        # Determine suggested next action based on results
        suggested_next = None
        suggested_action = None

        if result.risk_score > 50:
            suggested_next = "openrewrite"
            suggested_action = "analyze_migration"
        elif result.risk_score > 0:
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

    async def _explain_impacts(self, context: AgentContext, **kwargs) -> AgentResult:
        """Use LLM to explain each impact in detail."""
        impacts = kwargs.get("impacts", [])
        llm_provider = kwargs.get("llm_provider")

        if not impacts:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="explain_impacts",
                error="No impacts provided. Run analyze_impact first.",
            )

        if not llm_service.available_providers:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="explain_impacts",
                error="No LLM providers configured. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY.",
            )

        logger.info(f"[AnalysisAgent] Explaining {len(impacts)} impacts with LLM")
        explained_impacts = []

        for i, impact in enumerate(impacts):
            logger.info(f"[AnalysisAgent] Explaining impact {i+1}/{len(impacts)}")
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
                explained_impacts.append({
                    **impact,
                    "llm_explanation": explanation,
                })
            except Exception as e:
                logger.warning(f"[AnalysisAgent] Failed to explain impact: {e}")
                explained_impacts.append({
                    **impact,
                    "llm_explanation": {"error": str(e)},
                })

        logger.info(f"[AnalysisAgent] Explained {len(explained_impacts)} impacts")

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="explain_impacts",
            data={
                "total_explained": len(explained_impacts),
                "impacts": explained_impacts,
            },
            suggested_next_agent="analysis",
            suggested_next_action="generate_fixes",
        )

    async def _generate_fixes(self, context: AgentContext, **kwargs) -> AgentResult:
        """Use LLM to generate code fixes for each impact."""
        impacts = kwargs.get("impacts", [])
        llm_provider = kwargs.get("llm_provider")

        if not impacts:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="generate_fixes",
                error="No impacts provided. Run analyze_impact first.",
            )

        if not llm_service.available_providers:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="generate_fixes",
                error="No LLM providers configured.",
            )

        logger.info(f"[AnalysisAgent] Generating fixes for {len(impacts)} impacts")
        impacts_with_fixes = []

        for i, impact in enumerate(impacts):
            logger.info(f"[AnalysisAgent] Generating fix {i+1}/{len(impacts)}")
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
                logger.warning(f"[AnalysisAgent] Failed to generate fix: {e}")
                impacts_with_fixes.append({
                    **impact,
                    "fix": {"error": str(e)},
                })

        logger.info(f"[AnalysisAgent] Generated {len(impacts_with_fixes)} fixes")

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="generate_fixes",
            data={
                "total_fixes": len(impacts_with_fixes),
                "impacts_with_fixes": impacts_with_fixes,
            },
            suggested_next_agent="analysis",
            suggested_next_action="create_patch",
        )

    async def _create_patch(self, context: AgentContext, **kwargs) -> AgentResult:
        """Generate unified diff patches for all fixes."""
        repo_path = Path(kwargs.get("repository_path", ""))
        impacts_with_fixes = kwargs.get("impacts_with_fixes", [])
        llm_provider = kwargs.get("llm_provider")

        if not impacts_with_fixes:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="create_patch",
                error="No impacts with fixes provided. Run generate_fixes first.",
            )

        if not llm_service.available_providers:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="create_patch",
                error="No LLM providers configured.",
            )

        logger.info(f"[AnalysisAgent] Creating patches for {len(impacts_with_fixes)} fixes")

        # Group impacts by file
        by_file: dict[str, list] = {}
        for impact in impacts_with_fixes:
            file_path = impact.get("file_path", "")
            if file_path not in by_file:
                by_file[file_path] = []
            by_file[file_path].append(impact)

        patches = []
        for file_path, file_impacts in by_file.items():
            logger.info(f"[AnalysisAgent] Creating patch for {file_path}")
            try:
                original_content = Path(file_path).read_text()
                patch = await llm_service.generate_patch(
                    file_path=file_path,
                    original_content=original_content,
                    impacts_with_fixes=file_impacts,
                    provider=llm_provider,
                )
                patches.append({
                    "file_path": file_path,
                    "patch": patch,
                })
            except Exception as e:
                logger.warning(f"[AnalysisAgent] Failed to create patch for {file_path}: {e}")
                patches.append({
                    "file_path": file_path,
                    "patch": {"error": str(e)},
                })

        logger.info(f"[AnalysisAgent] Created {len(patches)} patches")

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="create_patch",
            data={
                "total_files": len(patches),
                "patches": patches,
            },
        )

    async def _full_analysis(self, context: AgentContext, **kwargs) -> AgentResult:
        """Run complete analysis pipeline: analyze -> explain -> fix -> patch."""
        repo_path = kwargs.get("repository_path")
        from_version = kwargs.get("from_version")
        to_version = kwargs.get("to_version")
        llm_provider = kwargs.get("llm_provider")

        logger.info(f"[AnalysisAgent] Starting full analysis pipeline")
        logger.info(f"[AnalysisAgent] Repository: {repo_path}")
        logger.info(f"[AnalysisAgent] Versions: {from_version} -> {to_version}")

        # Step 1: Analyze impact
        logger.info("[AnalysisAgent] Step 1/4: Analyzing impact...")
        impact_result = await self._analyze_impact(
            context,
            repository_path=repo_path,
            from_version=from_version,
            to_version=to_version,
        )

        if not impact_result.success:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="full_analysis",
                error=f"Impact analysis failed: {impact_result.error}",
            )

        impacts = impact_result.data.get("impacts", [])
        if not impacts:
            return AgentResult(
                success=True,
                agent_name=self.name,
                action="full_analysis",
                data={
                    "message": "No impacts found - code is compatible!",
                    "risk_score": 0,
                    "risk_level": "low",
                },
            )

        # Step 2: Explain impacts with LLM
        logger.info("[AnalysisAgent] Step 2/4: Explaining impacts with LLM...")
        if llm_service.available_providers:
            explain_result = await self._explain_impacts(
                context,
                impacts=impacts,
                llm_provider=llm_provider,
            )
            if explain_result.success:
                impacts = explain_result.data.get("impacts", impacts)

        # Step 3: Generate fixes with LLM
        logger.info("[AnalysisAgent] Step 3/4: Generating fixes with LLM...")
        if llm_service.available_providers:
            fix_result = await self._generate_fixes(
                context,
                impacts=impacts,
                llm_provider=llm_provider,
            )
            if fix_result.success:
                impacts = fix_result.data.get("impacts_with_fixes", impacts)

        # Step 4: Create patches
        logger.info("[AnalysisAgent] Step 4/4: Creating patches...")
        patches = []
        if llm_service.available_providers:
            patch_result = await self._create_patch(
                context,
                repository_path=repo_path,
                impacts_with_fixes=impacts,
                llm_provider=llm_provider,
            )
            if patch_result.success:
                patches = patch_result.data.get("patches", [])

        logger.info("[AnalysisAgent] Full analysis complete")

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="full_analysis",
            data={
                "from_version": from_version,
                "to_version": to_version,
                "risk_score": impact_result.data.get("risk_score", 0),
                "risk_level": impact_result.data.get("risk_level", "unknown"),
                "total_impacts": len(impacts),
                "impacts": impacts,
                "patches": patches,
                "summary": impact_result.data.get("summary"),
            },
            warnings=impact_result.warnings,
        )

    def _group_by_type(self, changes) -> dict:
        """Group changes by type."""
        groups: dict[str, int] = {}
        for change in changes:
            type_str = change.change_type.value if hasattr(change.change_type, 'value') else str(change.change_type)
            groups[type_str] = groups.get(type_str, 0) + 1
        return groups

    def _generate_warnings(self, result) -> list[str]:
        """Generate warnings based on analysis result."""
        warnings = []
        from app.models.analysis import RiskLevel

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

    def _generate_recommendation(self, steps) -> str:
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

    def _parse_version(self, version: str) -> tuple[int, int, int] | None:
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
        # Check if we can reach release notes sources
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get("https://api.adoptium.net/v3/info/available_releases")
                return resp.status_code == 200
        except Exception:
            return False
