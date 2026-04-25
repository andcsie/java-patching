"""Release Notes Agent - Fetches and parses JDK release notes."""

import logging

from app.agents.base import Agent, AgentAction, AgentCapability, AgentContext, AgentResult
from app.agents.bus import AgentMessage, MessageType, agent_bus
from app.agents.registry import register_agent
from app.services.release_notes_service import release_notes_service

logger = logging.getLogger(__name__)


@register_agent
class ReleaseNotesAgent(Agent):
    """Agent for fetching JDK release notes.

    Capabilities:
    - Fetch release notes from Oracle, OpenJDK, Adoptium
    - Parse changes between versions
    - Identify security fixes (CVEs)
    - Categorize changes (deprecated, removed, behavioral)

    Communicates results via AgentBus for downstream agents.
    """

    name = "release_notes"
    description = "JDK release notes fetching and parsing"
    version = "1.0.0"

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability.SECURITY_SCANNING,
        ]

    @property
    def actions(self) -> list[AgentAction]:
        return [
            AgentAction(
                name="fetch_notes",
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
                name="get_security_fixes",
                description="Get security fixes (CVEs) between versions",
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
            ),
            AgentAction(
                name="get_deprecated_apis",
                description="Get deprecated APIs between versions",
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
            ),
        ]

    async def execute(self, action: str, context: AgentContext, **kwargs) -> AgentResult:
        """Execute a release notes action."""
        try:
            if action == "fetch_notes":
                return await self._fetch_notes(context, **kwargs)
            elif action == "get_security_fixes":
                return await self._get_security_fixes(context, **kwargs)
            elif action == "get_deprecated_apis":
                return await self._get_deprecated_apis(context, **kwargs)
            else:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    action=action,
                    error=f"Unknown action: {action}",
                )
        except Exception as e:
            logger.error(f"[ReleaseNotes] Action {action} failed: {e}")
            return AgentResult(
                success=False,
                agent_name=self.name,
                action=action,
                error=str(e),
            )

    async def _fetch_notes(self, context: AgentContext, **kwargs) -> AgentResult:
        """Fetch release notes between versions."""
        from_version = kwargs["from_version"]
        to_version = kwargs["to_version"]

        logger.info(f"[ReleaseNotes] Fetching notes: {from_version} -> {to_version}")

        changes = await release_notes_service.get_changes_between_versions(
            from_version,
            to_version,
        )

        logger.info(f"[ReleaseNotes] Found {len(changes)} changes")

        changes_data = [
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
        ]

        # Group by type
        by_type: dict[str, int] = {}
        for change in changes_data:
            change_type = change["type"]
            by_type[change_type] = by_type.get(change_type, 0) + 1

        result_data = {
            "from_version": from_version,
            "to_version": to_version,
            "total_changes": len(changes),
            "changes": changes_data,
            "by_type": by_type,
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
            action="fetch_notes",
            data=result_data,
            suggested_next_agent="impact",
            suggested_next_action="analyze",
        )

    async def _get_security_fixes(self, context: AgentContext, **kwargs) -> AgentResult:
        """Get security fixes between versions."""
        from_version = kwargs["from_version"]
        to_version = kwargs["to_version"]

        changes = await release_notes_service.get_changes_between_versions(
            from_version,
            to_version,
        )

        # Filter to security changes
        from app.models.analysis import ChangeType
        security_changes = [c for c in changes if c.change_type == ChangeType.SECURITY]

        cves = [c.cve_id for c in security_changes if c.cve_id]

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="get_security_fixes",
            data={
                "from_version": from_version,
                "to_version": to_version,
                "total_security_fixes": len(security_changes),
                "cves": cves,
                "fixes": [
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

    async def _get_deprecated_apis(self, context: AgentContext, **kwargs) -> AgentResult:
        """Get deprecated APIs between versions."""
        from_version = kwargs["from_version"]
        to_version = kwargs["to_version"]

        changes = await release_notes_service.get_changes_between_versions(
            from_version,
            to_version,
        )

        # Filter to deprecation changes
        from app.models.analysis import ChangeType
        deprecated = [c for c in changes if c.change_type in [ChangeType.DEPRECATED, ChangeType.REMOVED]]

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="get_deprecated_apis",
            data={
                "from_version": from_version,
                "to_version": to_version,
                "total_deprecated": len(deprecated),
                "apis": [
                    {
                        "version": c.version,
                        "type": c.change_type.value if hasattr(c.change_type, 'value') else str(c.change_type),
                        "component": c.component,
                        "description": c.description,
                        "affected_classes": c.affected_classes,
                        "affected_methods": c.affected_methods,
                        "migration_notes": c.migration_notes,
                    }
                    for c in deprecated
                ],
            },
        )

    async def health_check(self) -> bool:
        """Check if release notes agent is healthy."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get("https://api.adoptium.net/v3/info/available_releases")
                return resp.status_code == 200
        except Exception:
            return False
