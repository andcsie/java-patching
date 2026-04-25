"""Orchestrator Agent - Coordinates multi-agent workflows via the AgentBus."""

import logging
from datetime import datetime
from uuid import UUID

from app.agents.base import Agent, AgentAction, AgentCapability, AgentContext, AgentResult
from app.agents.bus import AgentMessage, MessageType, WorkflowContext, agent_bus
from app.agents.registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class OrchestratorAgent(Agent):
    """Central orchestrator for multi-agent JDK upgrade workflows.

    Coordinates specialized agents:
    - scanner: Scans repository for Java files
    - release_notes: Fetches JDK release notes
    - impact: Analyzes code impacts
    - explainer: LLM-powered impact explanations
    - fixer: LLM-powered code fix generation
    - patcher: Creates unified diff patches
    - renovate: Version bumping (patch upgrades)
    - openrewrite: Recipe-based transformations (major upgrades)

    Workflows:
    - full_upgrade: Complete JDK upgrade pipeline
    - quick_scan: Fast impact assessment
    - patch_upgrade: Simple version bump
    - major_upgrade: Full migration with OpenRewrite
    """

    name = "orchestrator"
    description = "Multi-agent workflow coordinator for JDK upgrades"
    version = "1.0.0"

    def __init__(self):
        self._active_workflows: dict[UUID, dict] = {}
        self._setup_subscriptions()

    def _setup_subscriptions(self):
        """Subscribe to agent completion events."""
        agent_bus.subscribe("scanner.complete", self._on_scan_complete)
        agent_bus.subscribe("release_notes.complete", self._on_release_notes_complete)
        agent_bus.subscribe("impact.complete", self._on_impact_complete)
        agent_bus.subscribe("explainer.complete", self._on_explain_complete)
        agent_bus.subscribe("fixer.complete", self._on_fix_complete)
        agent_bus.subscribe("patcher.complete", self._on_patch_complete)
        agent_bus.subscribe("*", self._log_all_events)

    async def _log_all_events(self, message: AgentMessage, workflow: WorkflowContext | None):
        """Log all events for debugging."""
        logger.debug(f"[Orchestrator] Event: {message.from_agent}.{message.action}")

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability.IMPACT_ANALYSIS,
            AgentCapability.CODE_MIGRATION,
            AgentCapability.VERSION_BUMPING,
        ]

    @property
    def actions(self) -> list[AgentAction]:
        return [
            AgentAction(
                name="full_upgrade",
                description="Run complete JDK upgrade pipeline: scan -> analyze -> explain -> fix -> patch",
                parameters={
                    "type": "object",
                    "properties": {
                        "repository_path": {
                            "type": "string",
                            "description": "Path to the repository",
                        },
                        "from_version": {
                            "type": "string",
                            "description": "Current JDK version (e.g., '11.0.18')",
                        },
                        "to_version": {
                            "type": "string",
                            "description": "Target JDK version (e.g., '11.0.22')",
                        },
                        "llm_provider": {
                            "type": "string",
                            "description": "LLM provider to use (optional)",
                        },
                        "include_version_bump": {
                            "type": "boolean",
                            "description": "Include Renovate version bump",
                            "default": True,
                        },
                    },
                    "required": ["repository_path", "from_version", "to_version"],
                },
            ),
            AgentAction(
                name="quick_scan",
                description="Fast impact assessment without LLM processing",
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
                    },
                    "required": ["repository_path", "from_version", "to_version"],
                },
            ),
            AgentAction(
                name="patch_upgrade",
                description="Simple patch version upgrade using Renovate",
                parameters={
                    "type": "object",
                    "properties": {
                        "repository_path": {
                            "type": "string",
                            "description": "Path to the repository",
                        },
                        "target_version": {
                            "type": "string",
                            "description": "Target patch version",
                        },
                        "apply": {
                            "type": "boolean",
                            "description": "Apply changes (false = preview only)",
                            "default": False,
                        },
                    },
                    "required": ["repository_path", "target_version"],
                },
            ),
            AgentAction(
                name="major_upgrade",
                description="Major version upgrade using OpenRewrite recipes",
                parameters={
                    "type": "object",
                    "properties": {
                        "repository_path": {
                            "type": "string",
                            "description": "Path to the repository",
                        },
                        "from_major": {
                            "type": "integer",
                            "description": "Current major version (e.g., 11)",
                        },
                        "to_major": {
                            "type": "integer",
                            "description": "Target major version (e.g., 17)",
                        },
                        "dry_run": {
                            "type": "boolean",
                            "description": "Preview changes only",
                            "default": True,
                        },
                    },
                    "required": ["repository_path", "from_major", "to_major"],
                },
            ),
            AgentAction(
                name="get_workflow_status",
                description="Get status of a running workflow",
                parameters={
                    "type": "object",
                    "properties": {
                        "workflow_id": {
                            "type": "string",
                            "description": "Workflow ID to check",
                        },
                    },
                    "required": ["workflow_id"],
                },
            ),
        ]

    async def execute(self, action: str, context: AgentContext, **kwargs) -> AgentResult:
        """Execute an orchestration action."""
        try:
            if action == "full_upgrade":
                return await self._full_upgrade(context, **kwargs)
            elif action == "quick_scan":
                return await self._quick_scan(context, **kwargs)
            elif action == "patch_upgrade":
                return await self._patch_upgrade(context, **kwargs)
            elif action == "major_upgrade":
                return await self._major_upgrade(context, **kwargs)
            elif action == "get_workflow_status":
                return await self._get_workflow_status(context, **kwargs)
            else:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    action=action,
                    error=f"Unknown action: {action}",
                )
        except Exception as e:
            logger.error(f"[Orchestrator] Action {action} failed: {e}")
            return AgentResult(
                success=False,
                agent_name=self.name,
                action=action,
                error=str(e),
            )

    async def _full_upgrade(self, context: AgentContext, **kwargs) -> AgentResult:
        """Run complete upgrade pipeline using specialized agents."""
        from app.agents.registry import agent_registry

        repo_path = kwargs["repository_path"]
        from_version = kwargs["from_version"]
        to_version = kwargs["to_version"]
        llm_provider = kwargs.get("llm_provider")
        include_version_bump = kwargs.get("include_version_bump", True)

        # Create workflow context
        workflow = agent_bus.create_workflow(
            repository_path=repo_path,
            from_version=from_version,
            to_version=to_version,
            user_id=context.user_id,
        )

        logger.info(f"[Orchestrator] Starting full_upgrade workflow {workflow.workflow_id}")
        logger.info(f"[Orchestrator] Repository: {repo_path}")
        logger.info(f"[Orchestrator] Versions: {from_version} -> {to_version}")

        # Track workflow
        self._active_workflows[workflow.workflow_id] = {
            "status": "running",
            "started_at": datetime.utcnow(),
            "current_stage": "scanning",
            "stages_completed": [],
        }

        try:
            # Stage 1: Scan repository
            logger.info("[Orchestrator] Stage 1/6: Scanning repository...")
            workflow.current_stage = "scanning"
            scanner = agent_registry.get("scanner")
            if scanner:
                scan_result = await scanner.execute(
                    "scan_java_files",
                    context,
                    repository_path=repo_path,
                )
                if scan_result.success:
                    workflow.scan_result = scan_result.data
                    workflow.completed_stages.append("scanning")
                    await self._publish_stage_complete("scanner", "scan", scan_result.data, workflow.workflow_id)

            # Stage 2: Fetch release notes
            logger.info("[Orchestrator] Stage 2/6: Fetching release notes...")
            workflow.current_stage = "release_notes"
            release_notes_agent = agent_registry.get("release_notes")
            if release_notes_agent:
                notes_result = await release_notes_agent.execute(
                    "fetch_notes",
                    context,
                    from_version=from_version,
                    to_version=to_version,
                )
                if notes_result.success:
                    workflow.release_notes = notes_result.data.get("changes", [])
                    workflow.completed_stages.append("release_notes")
                    await self._publish_stage_complete("release_notes", "fetch", notes_result.data, workflow.workflow_id)

            # Stage 3: Analyze impacts
            logger.info("[Orchestrator] Stage 3/6: Analyzing impacts...")
            workflow.current_stage = "impact_analysis"
            impact_agent = agent_registry.get("impact")
            if impact_agent:
                impact_result = await impact_agent.execute(
                    "analyze",
                    context,
                    repository_path=repo_path,
                    from_version=from_version,
                    to_version=to_version,
                )
                if impact_result.success:
                    workflow.impacts = impact_result.data.get("impacts", [])
                    workflow.risk_score = impact_result.data.get("risk_score", 0)
                    workflow.risk_level = impact_result.data.get("risk_level", "unknown")
                    workflow.completed_stages.append("impact_analysis")
                    await self._publish_stage_complete("impact", "analyze", impact_result.data, workflow.workflow_id)

            # If no impacts, skip LLM stages
            if not workflow.impacts:
                logger.info("[Orchestrator] No impacts found - skipping LLM stages")
                agent_bus.complete_workflow(workflow.workflow_id)
                return AgentResult(
                    success=True,
                    agent_name=self.name,
                    action="full_upgrade",
                    data={
                        "workflow_id": str(workflow.workflow_id),
                        "message": "No impacts found - code is compatible!",
                        "risk_score": 0,
                        "risk_level": "low",
                        "stages_completed": workflow.completed_stages,
                    },
                )

            # Stage 4: Explain impacts with LLM
            logger.info("[Orchestrator] Stage 4/6: Explaining impacts with LLM...")
            workflow.current_stage = "explaining"
            explainer = agent_registry.get("explainer")
            if explainer:
                explain_result = await explainer.execute(
                    "explain",
                    context,
                    impacts=workflow.impacts,
                    llm_provider=llm_provider,
                )
                if explain_result.success:
                    workflow.explanations = explain_result.data.get("explained_impacts", [])
                    workflow.completed_stages.append("explaining")
                    await self._publish_stage_complete("explainer", "explain", explain_result.data, workflow.workflow_id)

            # Stage 5: Generate fixes with LLM
            logger.info("[Orchestrator] Stage 5/6: Generating fixes with LLM...")
            workflow.current_stage = "fixing"
            fixer = agent_registry.get("fixer")
            if fixer:
                # Use explained impacts if available, otherwise original impacts
                impacts_to_fix = workflow.explanations if workflow.explanations else workflow.impacts
                fix_result = await fixer.execute(
                    "generate_fixes",
                    context,
                    impacts=impacts_to_fix,
                    llm_provider=llm_provider,
                )
                if fix_result.success:
                    workflow.fixes = fix_result.data.get("impacts_with_fixes", [])
                    workflow.completed_stages.append("fixing")
                    await self._publish_stage_complete("fixer", "fix", fix_result.data, workflow.workflow_id)

            # Stage 6: Create patches
            logger.info("[Orchestrator] Stage 6/6: Creating patches...")
            workflow.current_stage = "patching"
            patcher = agent_registry.get("patcher")
            if patcher:
                impacts_for_patches = workflow.fixes if workflow.fixes else workflow.impacts
                patch_result = await patcher.execute(
                    "create_patches",
                    context,
                    repository_path=repo_path,
                    impacts_with_fixes=impacts_for_patches,
                    llm_provider=llm_provider,
                )
                if patch_result.success:
                    workflow.patches = patch_result.data.get("patches", [])
                    workflow.completed_stages.append("patching")
                    await self._publish_stage_complete("patcher", "patch", patch_result.data, workflow.workflow_id)

            # Optional: Version bump with Renovate
            if include_version_bump:
                logger.info("[Orchestrator] Bonus: Generating version bump...")
                renovate = agent_registry.get("renovate")
                if renovate:
                    bump_result = await renovate.execute(
                        "preview_version_bump",
                        context,
                        repository_path=repo_path,
                        target_version=to_version,
                    )
                    if bump_result.success:
                        workflow.version_bumps = bump_result.data.get("changes", [])
                        workflow.completed_stages.append("version_bump")

            # Complete workflow
            agent_bus.complete_workflow(workflow.workflow_id)
            self._active_workflows[workflow.workflow_id]["status"] = "completed"

            logger.info(f"[Orchestrator] Workflow {workflow.workflow_id} completed successfully")

            return AgentResult(
                success=True,
                agent_name=self.name,
                action="full_upgrade",
                data={
                    "workflow_id": str(workflow.workflow_id),
                    "from_version": from_version,
                    "to_version": to_version,
                    "risk_score": workflow.risk_score,
                    "risk_level": workflow.risk_level,
                    "total_impacts": len(workflow.impacts),
                    "impacts": workflow.fixes if workflow.fixes else workflow.impacts,
                    "explanations": workflow.explanations,
                    "patches": workflow.patches,
                    "version_bumps": workflow.version_bumps,
                    "stages_completed": workflow.completed_stages,
                },
            )

        except Exception as e:
            logger.error(f"[Orchestrator] Workflow failed: {e}")
            self._active_workflows[workflow.workflow_id]["status"] = "failed"
            self._active_workflows[workflow.workflow_id]["error"] = str(e)
            workflow.errors.append(str(e))
            raise

    async def _quick_scan(self, context: AgentContext, **kwargs) -> AgentResult:
        """Run quick impact scan without LLM processing."""
        from app.agents.registry import agent_registry

        repo_path = kwargs["repository_path"]
        from_version = kwargs["from_version"]
        to_version = kwargs["to_version"]

        logger.info(f"[Orchestrator] Quick scan: {repo_path}")

        # Use the impact agent directly
        impact_agent = agent_registry.get("impact")
        if not impact_agent:
            # Fall back to analysis agent
            analysis_agent = agent_registry.get("analysis")
            if analysis_agent:
                return await analysis_agent.execute(
                    "analyze_impact",
                    context,
                    repository_path=repo_path,
                    from_version=from_version,
                    to_version=to_version,
                )
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="quick_scan",
                error="No impact analysis agent available",
            )

        return await impact_agent.execute(
            "analyze",
            context,
            repository_path=repo_path,
            from_version=from_version,
            to_version=to_version,
        )

    async def _patch_upgrade(self, context: AgentContext, **kwargs) -> AgentResult:
        """Simple patch upgrade using Renovate agent."""
        from app.agents.registry import agent_registry

        repo_path = kwargs["repository_path"]
        target_version = kwargs["target_version"]
        apply = kwargs.get("apply", False)

        logger.info(f"[Orchestrator] Patch upgrade to {target_version}")

        renovate = agent_registry.get("renovate")
        if not renovate:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="patch_upgrade",
                error="Renovate agent not available",
            )

        if apply:
            return await renovate.execute(
                "apply_version_bump",
                context,
                repository_path=repo_path,
                target_version=target_version,
            )
        else:
            return await renovate.execute(
                "preview_version_bump",
                context,
                repository_path=repo_path,
                target_version=target_version,
            )

    async def _major_upgrade(self, context: AgentContext, **kwargs) -> AgentResult:
        """Major version upgrade using OpenRewrite."""
        from app.agents.registry import agent_registry

        repo_path = kwargs["repository_path"]
        from_major = kwargs["from_major"]
        to_major = kwargs["to_major"]
        dry_run = kwargs.get("dry_run", True)

        logger.info(f"[Orchestrator] Major upgrade: JDK {from_major} -> {to_major}")

        openrewrite = agent_registry.get("openrewrite")
        if not openrewrite:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="major_upgrade",
                error="OpenRewrite agent not available",
            )

        # Get suggested migration path
        path_result = await openrewrite.execute(
            "suggest_migration_path",
            context,
            from_version=from_major,
            to_version=to_major,
        )

        if not path_result.success:
            return path_result

        # Run each migration step
        steps = path_result.data.get("steps", [])
        results = []

        for step in steps:
            recipe = step.get("recipe")
            if recipe:
                step_result = await openrewrite.execute(
                    "run_recipe",
                    context,
                    repository_path=repo_path,
                    recipe=recipe,
                    dry_run=dry_run,
                )
                results.append({
                    "step": step,
                    "result": step_result.to_dict(),
                })

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="major_upgrade",
            data={
                "from_major": from_major,
                "to_major": to_major,
                "dry_run": dry_run,
                "migration_path": steps,
                "results": results,
            },
        )

    async def _get_workflow_status(self, context: AgentContext, **kwargs) -> AgentResult:
        """Get status of a workflow."""
        workflow_id_str = kwargs["workflow_id"]

        try:
            workflow_id = UUID(workflow_id_str)
        except ValueError:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="get_workflow_status",
                error="Invalid workflow ID format",
            )

        workflow = agent_bus.get_workflow(workflow_id)
        if not workflow:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="get_workflow_status",
                error="Workflow not found",
            )

        active = self._active_workflows.get(workflow_id, {})

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="get_workflow_status",
            data={
                "workflow_id": str(workflow_id),
                "status": active.get("status", "unknown"),
                "current_stage": workflow.current_stage,
                "completed_stages": workflow.completed_stages,
                "risk_score": workflow.risk_score,
                "risk_level": workflow.risk_level,
                "total_impacts": len(workflow.impacts),
                "errors": workflow.errors,
                "started_at": workflow.started_at.isoformat() if workflow.started_at else None,
                "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else None,
            },
        )

    async def _publish_stage_complete(
        self,
        agent_name: str,
        action: str,
        data: dict,
        workflow_id: UUID,
    ):
        """Publish a stage completion event."""
        message = AgentMessage(
            type=MessageType.EVENT,
            from_agent=agent_name,
            action="complete",
            payload=data,
        )
        await agent_bus.publish(message, workflow_id)

    # Event handlers for agent completions
    async def _on_scan_complete(self, message: AgentMessage, workflow: WorkflowContext | None):
        if workflow:
            workflow.scan_result = message.payload
            logger.info(f"[Orchestrator] Scan complete for workflow {workflow.workflow_id}")

    async def _on_release_notes_complete(self, message: AgentMessage, workflow: WorkflowContext | None):
        if workflow:
            workflow.release_notes = message.payload.get("changes", [])
            logger.info(f"[Orchestrator] Release notes fetched for workflow {workflow.workflow_id}")

    async def _on_impact_complete(self, message: AgentMessage, workflow: WorkflowContext | None):
        if workflow:
            workflow.impacts = message.payload.get("impacts", [])
            logger.info(f"[Orchestrator] Impact analysis complete for workflow {workflow.workflow_id}")

    async def _on_explain_complete(self, message: AgentMessage, workflow: WorkflowContext | None):
        if workflow:
            workflow.explanations = message.payload.get("explained_impacts", [])
            logger.info(f"[Orchestrator] Explanations complete for workflow {workflow.workflow_id}")

    async def _on_fix_complete(self, message: AgentMessage, workflow: WorkflowContext | None):
        if workflow:
            workflow.fixes = message.payload.get("impacts_with_fixes", [])
            logger.info(f"[Orchestrator] Fixes generated for workflow {workflow.workflow_id}")

    async def _on_patch_complete(self, message: AgentMessage, workflow: WorkflowContext | None):
        if workflow:
            workflow.patches = message.payload.get("patches", [])
            logger.info(f"[Orchestrator] Patches created for workflow {workflow.workflow_id}")

    async def health_check(self) -> bool:
        """Check if orchestrator is healthy."""
        return True
