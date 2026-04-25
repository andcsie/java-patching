"""Patcher Agent - Creates unified diff patches from fixes."""

import logging
from pathlib import Path

from app.agents.base import Agent, AgentAction, AgentCapability, AgentContext, AgentResult
from app.agents.bus import AgentMessage, MessageType, agent_bus
from app.agents.registry import register_agent
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


@register_agent
class PatcherAgent(Agent):
    """Agent for creating unified diff patches.

    Capabilities:
    - Create unified diff patches from fixes
    - Apply patches to files
    - Validate patch syntax
    - Preview patch effects

    Uses the LLM service for intelligent patch generation.
    Communicates results via AgentBus.
    """

    name = "patcher"
    description = "Unified diff patch creation and application"
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
                name="create_patches",
                description="Create unified diff patches for all fixes",
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
                    "required": ["impacts_with_fixes"],
                },
                required_capabilities=[AgentCapability.CODE_MIGRATION],
            ),
            AgentAction(
                name="create_single_patch",
                description="Create a patch for a single file",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file",
                        },
                        "original_content": {
                            "type": "string",
                            "description": "Original file content",
                        },
                        "impacts_with_fixes": {
                            "type": "array",
                            "description": "Impacts with fixes for this file",
                        },
                        "llm_provider": {
                            "type": "string",
                            "description": "LLM provider to use",
                        },
                    },
                    "required": ["file_path", "original_content", "impacts_with_fixes"],
                },
            ),
            AgentAction(
                name="apply_patch",
                description="Apply a patch to a file",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file",
                        },
                        "patch": {
                            "type": "string",
                            "description": "Unified diff patch content",
                        },
                        "dry_run": {
                            "type": "boolean",
                            "description": "Preview without applying",
                            "default": True,
                        },
                    },
                    "required": ["file_path", "patch"],
                },
            ),
            AgentAction(
                name="validate_patch",
                description="Validate a patch syntax",
                parameters={
                    "type": "object",
                    "properties": {
                        "patch": {
                            "type": "string",
                            "description": "Patch content to validate",
                        },
                    },
                    "required": ["patch"],
                },
            ),
        ]

    async def execute(self, action: str, context: AgentContext, **kwargs) -> AgentResult:
        """Execute a patching action."""
        try:
            if action == "create_patches":
                return await self._create_patches(context, **kwargs)
            elif action == "create_single_patch":
                return await self._create_single_patch(context, **kwargs)
            elif action == "apply_patch":
                return await self._apply_patch(context, **kwargs)
            elif action == "validate_patch":
                return await self._validate_patch(context, **kwargs)
            else:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    action=action,
                    error=f"Unknown action: {action}",
                )
        except Exception as e:
            logger.error(f"[Patcher] Action {action} failed: {e}")
            return AgentResult(
                success=False,
                agent_name=self.name,
                action=action,
                error=str(e),
            )

    async def _create_patches(self, context: AgentContext, **kwargs) -> AgentResult:
        """Create patches for all fixes."""
        repo_path = Path(kwargs.get("repository_path", ""))
        impacts_with_fixes = kwargs.get("impacts_with_fixes", [])
        llm_provider = kwargs.get("llm_provider")

        if not impacts_with_fixes:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="create_patches",
                error="No impacts with fixes provided. Run generate_fixes first.",
            )

        if not llm_service.available_providers:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="create_patches",
                error="No LLM providers configured.",
            )

        logger.info(f"[Patcher] Creating patches for {len(impacts_with_fixes)} fixes")

        # Group impacts by file
        by_file: dict[str, list] = {}
        for impact in impacts_with_fixes:
            file_path = impact.get("file_path", "")
            if file_path not in by_file:
                by_file[file_path] = []
            by_file[file_path].append(impact)

        patches = []
        for file_path, file_impacts in by_file.items():
            logger.info(f"[Patcher] Creating patch for {file_path}")
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
                    "impacts_count": len(file_impacts),
                    "patch": patch,
                })
            except Exception as e:
                logger.warning(f"[Patcher] Failed to create patch for {file_path}: {e}")
                patches.append({
                    "file_path": file_path,
                    "impacts_count": len(file_impacts),
                    "patch": {"error": str(e)},
                })

        logger.info(f"[Patcher] Created {len(patches)} patches")

        # Count successful patches
        successful_patches = sum(
            1 for p in patches
            if p.get("patch") and not p["patch"].get("error")
        )

        result_data = {
            "total_files": len(patches),
            "successful_patches": successful_patches,
            "patches": patches,
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
            action="create_patches",
            data=result_data,
        )

    async def _create_single_patch(self, context: AgentContext, **kwargs) -> AgentResult:
        """Create a patch for a single file."""
        file_path = kwargs.get("file_path", "")
        original_content = kwargs.get("original_content", "")
        impacts_with_fixes = kwargs.get("impacts_with_fixes", [])
        llm_provider = kwargs.get("llm_provider")

        if not llm_service.available_providers:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="create_single_patch",
                error="No LLM providers configured.",
            )

        try:
            patch = await llm_service.generate_patch(
                file_path=file_path,
                original_content=original_content,
                impacts_with_fixes=impacts_with_fixes,
                provider=llm_provider,
            )

            return AgentResult(
                success=True,
                agent_name=self.name,
                action="create_single_patch",
                data={
                    "file_path": file_path,
                    "patch": patch,
                },
            )
        except Exception as e:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="create_single_patch",
                error=str(e),
            )

    async def _apply_patch(self, context: AgentContext, **kwargs) -> AgentResult:
        """Apply a patch to a file."""
        file_path = kwargs.get("file_path", "")
        patch_content = kwargs.get("patch", "")
        dry_run = kwargs.get("dry_run", True)

        if not file_path or not patch_content:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="apply_patch",
                error="File path and patch content are required",
            )

        # For now, return preview
        # In production, would use subprocess to apply patch
        if dry_run:
            return AgentResult(
                success=True,
                agent_name=self.name,
                action="apply_patch",
                data={
                    "mode": "dry_run",
                    "file_path": file_path,
                    "patch_preview": patch_content,
                },
                warnings=["Dry run mode - patch not applied"],
            )

        # Apply patch using subprocess
        import subprocess
        import tempfile

        try:
            # Write patch to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as f:
                f.write(patch_content)
                patch_file = f.name

            # Apply patch
            result = subprocess.run(
                ["patch", "-p0", "--dry-run", "-i", patch_file],
                capture_output=True,
                text=True,
                cwd=Path(file_path).parent,
            )

            if result.returncode != 0:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    action="apply_patch",
                    error=f"Patch failed: {result.stderr}",
                )

            # Actually apply
            result = subprocess.run(
                ["patch", "-p0", "-i", patch_file],
                capture_output=True,
                text=True,
                cwd=Path(file_path).parent,
            )

            return AgentResult(
                success=True,
                agent_name=self.name,
                action="apply_patch",
                data={
                    "mode": "applied",
                    "file_path": file_path,
                    "output": result.stdout,
                },
            )

        except FileNotFoundError:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="apply_patch",
                error="patch command not found",
            )
        except Exception as e:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="apply_patch",
                error=str(e),
            )

    async def _validate_patch(self, context: AgentContext, **kwargs) -> AgentResult:
        """Validate patch syntax."""
        patch = kwargs.get("patch", "")

        issues = []
        warnings = []

        if not patch:
            issues.append("Patch content is empty")
            return AgentResult(
                success=True,
                agent_name=self.name,
                action="validate_patch",
                data={"valid": False, "issues": issues},
            )

        lines = patch.split("\n")

        # Check for unified diff header
        has_header = any(line.startswith("---") for line in lines)
        has_new = any(line.startswith("+++") for line in lines)
        has_hunks = any(line.startswith("@@") for line in lines)

        if not has_header:
            issues.append("Missing '---' header line")
        if not has_new:
            issues.append("Missing '+++' header line")
        if not has_hunks:
            issues.append("Missing '@@ ... @@' hunk headers")

        # Check for malformed hunks
        for i, line in enumerate(lines):
            if line.startswith("@@"):
                # Should match @@ -X,Y +A,B @@
                import re
                if not re.match(r"@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", line):
                    warnings.append(f"Line {i+1}: Potentially malformed hunk header")

        is_valid = len(issues) == 0

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="validate_patch",
            data={
                "valid": is_valid,
                "issues": issues,
                "warnings": warnings,
            },
        )

    async def health_check(self) -> bool:
        """Check if patcher agent is healthy."""
        return bool(llm_service.available_providers)
