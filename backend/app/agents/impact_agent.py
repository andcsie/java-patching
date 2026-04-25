"""Impact Agent - Analyzes code for JDK upgrade impacts."""

import logging
from pathlib import Path

from app.agents.base import Agent, AgentAction, AgentCapability, AgentContext, AgentResult
from app.agents.bus import AgentMessage, MessageType, agent_bus
from app.agents.registry import register_agent
from app.services.analyzer_service import analyzer_service

logger = logging.getLogger(__name__)


@register_agent
class ImpactAgent(Agent):
    """Agent for analyzing JDK upgrade impacts on code.

    Capabilities:
    - Analyze code against release notes changes
    - Calculate risk scores
    - Identify affected files and methods
    - Generate impact reports

    Communicates results via AgentBus for downstream agents.
    """

    name = "impact"
    description = "Code impact analysis for JDK upgrades"
    version = "1.0.0"

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability.IMPACT_ANALYSIS,
            AgentCapability.SECURITY_SCANNING,
        ]

    @property
    def actions(self) -> list[AgentAction]:
        return [
            AgentAction(
                name="analyze",
                description="Analyze repository for JDK upgrade impacts",
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
                required_capabilities=[AgentCapability.IMPACT_ANALYSIS],
            ),
            AgentAction(
                name="get_risk_summary",
                description="Get a summary of risk for an upgrade",
                parameters={
                    "type": "object",
                    "properties": {
                        "impacts": {
                            "type": "array",
                            "description": "List of impacts from analyze action",
                        },
                    },
                    "required": ["impacts"],
                },
            ),
        ]

    async def execute(self, action: str, context: AgentContext, **kwargs) -> AgentResult:
        """Execute an impact analysis action."""
        try:
            if action == "analyze":
                return await self._analyze(context, **kwargs)
            elif action == "get_risk_summary":
                return await self._get_risk_summary(context, **kwargs)
            else:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    action=action,
                    error=f"Unknown action: {action}",
                )
        except Exception as e:
            logger.error(f"[Impact] Action {action} failed: {e}")
            return AgentResult(
                success=False,
                agent_name=self.name,
                action=action,
                error=str(e),
            )

    async def _analyze(self, context: AgentContext, **kwargs) -> AgentResult:
        """Analyze repository for JDK upgrade impacts."""
        repo_path = Path(kwargs["repository_path"])
        from_version = kwargs["from_version"]
        to_version = kwargs["to_version"]

        logger.info(f"[Impact] Analyzing: {repo_path}")
        logger.info(f"[Impact] Versions: {from_version} -> {to_version}")

        result = await analyzer_service.analyze_repository(
            repo_path,
            from_version,
            to_version,
        )

        if result.error_message:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="analyze",
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

        logger.info(f"[Impact] Found {len(impacts_data)} impacts, risk_score={result.risk_score}")

        result_data = {
            "from_version": from_version,
            "to_version": to_version,
            "risk_score": result.risk_score,
            "risk_level": result.risk_level.value if hasattr(result.risk_level, 'value') else str(result.risk_level),
            "total_files_analyzed": result.total_files_analyzed,
            "total_impacts": len(impacts_data),
            "impacts": impacts_data,
            "summary": result.summary,
            "suggestions": result.suggestions,
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

        # Suggest next action based on results
        suggested_next = None
        suggested_action = None

        if impacts_data:
            suggested_next = "explainer"
            suggested_action = "explain"
        elif result.risk_score == 0:
            suggested_next = "renovate"
            suggested_action = "preview_version_bump"

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="analyze",
            data=result_data,
            warnings=self._generate_warnings(result),
            suggested_next_agent=suggested_next,
            suggested_next_action=suggested_action,
        )

    async def _get_risk_summary(self, context: AgentContext, **kwargs) -> AgentResult:
        """Get risk summary for impacts."""
        impacts = kwargs.get("impacts", [])

        if not impacts:
            return AgentResult(
                success=True,
                agent_name=self.name,
                action="get_risk_summary",
                data={
                    "total_impacts": 0,
                    "risk_score": 0,
                    "risk_level": "low",
                    "message": "No impacts - safe to upgrade",
                },
            )

        # Count by severity
        by_severity: dict[str, int] = {}
        by_type: dict[str, int] = {}

        for impact in impacts:
            severity = impact.get("severity", "unknown")
            change_type = impact.get("change_type", "unknown")

            by_severity[severity] = by_severity.get(severity, 0) + 1
            by_type[change_type] = by_type.get(change_type, 0) + 1

        # Calculate risk score
        score = 0
        score += by_severity.get("critical", 0) * 30
        score += by_severity.get("high", 0) * 20
        score += by_severity.get("medium", 0) * 10
        score += by_severity.get("low", 0) * 5
        score = min(score, 100)

        # Determine risk level
        if score >= 70:
            risk_level = "critical"
        elif score >= 50:
            risk_level = "high"
        elif score >= 25:
            risk_level = "medium"
        else:
            risk_level = "low"

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="get_risk_summary",
            data={
                "total_impacts": len(impacts),
                "risk_score": score,
                "risk_level": risk_level,
                "by_severity": by_severity,
                "by_type": by_type,
            },
        )

    def _generate_warnings(self, result) -> list[str]:
        """Generate warnings based on analysis result."""
        warnings = []
        from app.models.analysis import RiskLevel

        if result.risk_level == RiskLevel.CRITICAL:
            warnings.append("CRITICAL: This upgrade will likely break the build")
        elif result.risk_level == RiskLevel.HIGH:
            warnings.append("HIGH: Significant changes required before upgrade")

        critical_count = sum(
            1 for i in result.impacts
            if i.severity == RiskLevel.CRITICAL
        )
        if critical_count > 0:
            warnings.append(f"{critical_count} critical issues must be resolved")

        return warnings

    async def health_check(self) -> bool:
        """Check if impact agent is healthy."""
        return True
