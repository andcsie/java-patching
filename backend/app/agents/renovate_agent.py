"""Renovate Agent for JDK version management and patch automation."""

from pathlib import Path

from app.agents.base import Agent, AgentAction, AgentCapability, AgentContext, AgentResult
from app.agents.registry import register_agent
from app.services.renovate_service import RenovateService


@register_agent
class RenovateAgent(Agent):
    """Agent for Renovate-style JDK version management.

    Capabilities:
    - Detect JDK versions from build files (pom.xml, build.gradle, etc.)
    - Discover available patch versions from Adoptium API
    - Generate and apply version bumps
    - Generate Renovate configuration files

    Best for: Patch-level upgrades within the same major version (e.g., 11.0.18 → 11.0.22)
    """

    name = "renovate"
    description = "JDK version management and patch automation (Renovate-style)"
    version = "1.0.0"

    def __init__(self):
        self._service = RenovateService()

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability.VERSION_DETECTION,
            AgentCapability.PATCH_DISCOVERY,
            AgentCapability.VERSION_BUMPING,
            AgentCapability.CONFIG_GENERATION,
            AgentCapability.BUILD_TOOL_SUPPORT,
        ]

    @property
    def actions(self) -> list[AgentAction]:
        return [
            AgentAction(
                name="detect_version",
                description="Detect the current JDK version from build files in a repository",
                parameters={
                    "type": "object",
                    "properties": {
                        "repository_path": {
                            "type": "string",
                            "description": "Path to the repository to analyze",
                        },
                    },
                    "required": ["repository_path"],
                },
                required_capabilities=[AgentCapability.VERSION_DETECTION],
            ),
            AgentAction(
                name="get_available_patches",
                description="Get available patch versions for the current JDK major version",
                parameters={
                    "type": "object",
                    "properties": {
                        "repository_path": {
                            "type": "string",
                            "description": "Path to the repository",
                        },
                        "include_ea": {
                            "type": "boolean",
                            "description": "Include early access releases",
                            "default": False,
                        },
                    },
                    "required": ["repository_path"],
                },
                required_capabilities=[AgentCapability.PATCH_DISCOVERY],
            ),
            AgentAction(
                name="preview_version_bump",
                description="Preview changes needed to bump JDK version",
                parameters={
                    "type": "object",
                    "properties": {
                        "repository_path": {
                            "type": "string",
                            "description": "Path to the repository",
                        },
                        "target_version": {
                            "type": "string",
                            "description": "Target JDK version (e.g., '11.0.22')",
                        },
                    },
                    "required": ["repository_path", "target_version"],
                },
                required_capabilities=[AgentCapability.VERSION_BUMPING],
            ),
            AgentAction(
                name="apply_version_bump",
                description="Apply a version bump to update JDK version in build files",
                parameters={
                    "type": "object",
                    "properties": {
                        "repository_path": {
                            "type": "string",
                            "description": "Path to the repository",
                        },
                        "target_version": {
                            "type": "string",
                            "description": "Target JDK version to apply",
                        },
                    },
                    "required": ["repository_path", "target_version"],
                },
                required_capabilities=[AgentCapability.VERSION_BUMPING],
            ),
            AgentAction(
                name="generate_config",
                description="Generate a renovate.json configuration file for the repository",
                parameters={
                    "type": "object",
                    "properties": {
                        "repository_path": {
                            "type": "string",
                            "description": "Path to the repository",
                        },
                        "target_jdk": {
                            "type": "string",
                            "description": "Optional maximum JDK version constraint",
                        },
                        "save": {
                            "type": "boolean",
                            "description": "Save the config to renovate.json",
                            "default": False,
                        },
                    },
                    "required": ["repository_path"],
                },
                required_capabilities=[AgentCapability.CONFIG_GENERATION],
            ),
        ]

    async def execute(self, action: str, context: AgentContext, **kwargs) -> AgentResult:
        """Execute a Renovate action."""
        try:
            if action == "detect_version":
                return await self._detect_version(context, **kwargs)
            elif action == "get_available_patches":
                return await self._get_available_patches(context, **kwargs)
            elif action == "preview_version_bump":
                return await self._preview_version_bump(context, **kwargs)
            elif action == "apply_version_bump":
                return await self._apply_version_bump(context, **kwargs)
            elif action == "generate_config":
                return await self._generate_config(context, **kwargs)
            else:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    action=action,
                    error=f"Unknown action: {action}",
                )
        except Exception as e:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action=action,
                error=str(e),
            )

    async def _detect_version(self, context: AgentContext, **kwargs) -> AgentResult:
        """Detect JDK version from repository."""
        repo_path = Path(kwargs["repository_path"])

        version = await self._service.detect_jdk_version(repo_path)

        if not version:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="detect_version",
                error="Could not detect JDK version. No supported build files found.",
                suggested_next_agent="openrewrite",
                suggested_next_action="analyze_build_files",
            )

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="detect_version",
            data={
                "major": version.major,
                "minor": version.minor,
                "patch": version.patch,
                "full": version.full,
                "source_file": version.source_file,
                "source_line": version.source_line,
            },
        )

    async def _get_available_patches(self, context: AgentContext, **kwargs) -> AgentResult:
        """Get available patches for current version."""
        repo_path = Path(kwargs["repository_path"])
        include_ea = kwargs.get("include_ea", False)

        version = await self._service.detect_jdk_version(repo_path)
        if not version:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="get_available_patches",
                error="Could not detect JDK version",
            )

        patches = await self._service.get_available_patches(version, include_ea)

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="get_available_patches",
            data={
                "current_version": version.full,
                "patches": [
                    {
                        "version": p.version,
                        "release_date": p.release_date,
                        "release_type": p.release_type,
                        "is_lts": p.is_lts,
                        "security_fixes": p.security_fixes,
                        "release_notes_url": p.release_notes_url,
                    }
                    for p in patches
                ],
            },
        )

    async def _preview_version_bump(self, context: AgentContext, **kwargs) -> AgentResult:
        """Preview version bump changes."""
        repo_path = Path(kwargs["repository_path"])
        target_version = kwargs["target_version"]

        bumps = await self._service.generate_version_bump(repo_path, target_version)

        if not bumps:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="preview_version_bump",
                error="Could not generate version bump. Ensure same major version.",
                warnings=["For major version upgrades, consider using OpenRewrite agent"],
                suggested_next_agent="openrewrite",
                suggested_next_action="migrate_jdk",
            )

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="preview_version_bump",
            data={
                "target_version": target_version,
                "changes": [
                    {
                        "file": bump.file_path,
                        "old_version": bump.old_version,
                        "new_version": bump.new_version,
                        "line_number": bump.line_number,
                        "diff": bump.diff,
                    }
                    for bump in bumps
                ],
            },
        )

    async def _apply_version_bump(self, context: AgentContext, **kwargs) -> AgentResult:
        """Apply version bump to files."""
        repo_path = Path(kwargs["repository_path"])
        target_version = kwargs["target_version"]

        bumps = await self._service.generate_version_bump(repo_path, target_version)

        if not bumps:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="apply_version_bump",
                error="Could not generate version bump",
            )

        applied = []
        failed = []

        for bump in bumps:
            success = await self._service.apply_version_bump(bump)
            if success:
                applied.append(bump.file_path)
            else:
                failed.append(bump.file_path)

        if failed:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="apply_version_bump",
                data={"applied": applied, "failed": failed},
                error=f"Failed to apply bump to: {', '.join(failed)}",
            )

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="apply_version_bump",
            data={
                "target_version": target_version,
                "applied_files": applied,
            },
        )

    async def _generate_config(self, context: AgentContext, **kwargs) -> AgentResult:
        """Generate Renovate configuration."""
        repo_path = Path(kwargs["repository_path"])
        target_jdk = kwargs.get("target_jdk")
        save = kwargs.get("save", False)

        config = await self._service.generate_renovate_config(repo_path, target_jdk)

        result_data = {"config": config}

        if save:
            config_path = await self._service.save_renovate_config(repo_path, config)
            result_data["saved_to"] = config_path

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="generate_config",
            data=result_data,
        )

    async def health_check(self) -> bool:
        """Check if Renovate agent is healthy."""
        # Verify we can reach Adoptium API
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get("https://api.adoptium.net/v3/info/available_releases")
                return resp.status_code == 200
        except Exception:
            return False
