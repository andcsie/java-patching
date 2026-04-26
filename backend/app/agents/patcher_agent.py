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
            AgentAction(
                name="apply_all_patches",
                description="Apply all generated patches to files",
                parameters={
                    "type": "object",
                    "properties": {
                        "repository_path": {
                            "type": "string",
                            "description": "Path to the repository",
                        },
                        "patches": {
                            "type": "array",
                            "description": "List of patches from create_patches",
                        },
                    },
                    "required": ["repository_path", "patches"],
                },
            ),
            AgentAction(
                name="create_pr",
                description="Create a git branch with patches, optionally push and create PR on GitHub/Bitbucket",
                parameters={
                    "type": "object",
                    "properties": {
                        "repository_path": {
                            "type": "string",
                            "description": "Path to the repository",
                        },
                        "patches": {
                            "type": "array",
                            "description": "List of patches to apply",
                        },
                        "from_version": {
                            "type": "string",
                            "description": "Current JDK version",
                        },
                        "to_version": {
                            "type": "string",
                            "description": "Target JDK version",
                        },
                        "branch_name": {
                            "type": "string",
                            "description": "Branch name (optional, auto-generated if not provided)",
                        },
                        "push": {
                            "type": "boolean",
                            "description": "Push branch to remote after commit",
                            "default": False,
                        },
                        "create_remote_pr": {
                            "type": "boolean",
                            "description": "Create PR on GitHub/Bitbucket (requires push=true)",
                            "default": False,
                        },
                        "run_tests_first": {
                            "type": "boolean",
                            "description": "Run tests before creating PR (fails if tests fail)",
                            "default": False,
                        },
                        "pr_title": {
                            "type": "string",
                            "description": "PR title (optional, auto-generated if not provided)",
                        },
                        "pr_body": {
                            "type": "string",
                            "description": "PR body/description (optional)",
                        },
                    },
                    "required": ["repository_path", "patches", "from_version", "to_version"],
                },
            ),
            AgentAction(
                name="run_tests",
                description="Run Maven or Gradle tests to verify patches",
                parameters={
                    "type": "object",
                    "properties": {
                        "repository_path": {
                            "type": "string",
                            "description": "Path to the repository",
                        },
                    },
                    "required": ["repository_path"],
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
            elif action == "apply_all_patches":
                return await self._apply_all_patches(context, **kwargs)
            elif action == "create_pr":
                return await self._create_pr(context, **kwargs)
            elif action == "run_tests":
                return await self._run_tests(context, **kwargs)
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
            logger.info(f"[Patcher] Creating patch for {file_path} ({len(file_impacts)} impacts)")
            try:
                original_content = Path(file_path).read_text()

                # Generate patch programmatically (no LLM call, no batching needed)
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

    async def _apply_all_patches(self, context: AgentContext, **kwargs) -> AgentResult:
        """Apply all patches to files in the repository.

        Uses direct file modification instead of the patch command for reliability.
        Each patch contains the fixed code that replaces the original.
        """
        repo_path = Path(kwargs.get("repository_path", ""))
        patches = kwargs.get("patches", [])

        if not patches:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="apply_all_patches",
                error="No patches provided",
            )

        logger.info(f"[Patcher] Applying {len(patches)} patches to {repo_path}")

        applied = []
        failed = []

        for i, patch_info in enumerate(patches):
            file_path = patch_info.get("file_path", "")
            patch = patch_info.get("patch", {})

            logger.info(f"[Patcher] Processing patch {i+1}/{len(patches)}: {file_path}")

            if patch.get("error"):
                logger.warning(f"[Patcher] Patch has error: {patch['error']}")
                failed.append({"file": file_path, "error": patch["error"]})
                continue

            # Get the patched content from the patch data
            patched_content = patch.get("patched_content")
            unified_diff = patch.get("unified_diff", "")

            if not patched_content and not unified_diff:
                failed.append({"file": file_path, "error": "No patch content"})
                continue

            try:
                file_obj = Path(file_path)
                if not file_obj.exists():
                    failed.append({"file": file_path, "error": f"File not found: {file_path}"})
                    continue

                # Method 1: If we have patched_content, write it directly
                if patched_content:
                    logger.info(f"[Patcher] Writing patched content directly to {file_path}")
                    file_obj.write_text(patched_content)
                    applied.append({"file": file_path, "method": "direct_write"})
                    logger.info(f"[Patcher] Successfully patched {file_path}")
                    continue

                # Method 2: Apply unified diff manually
                if unified_diff:
                    logger.info(f"[Patcher] Applying unified diff to {file_path}")
                    original_content = file_obj.read_text()
                    patched = self._apply_unified_diff(original_content, unified_diff)

                    if patched is not None:
                        file_obj.write_text(patched)
                        applied.append({"file": file_path, "method": "unified_diff"})
                        logger.info(f"[Patcher] Successfully patched {file_path}")
                    else:
                        # Fallback: try subprocess patch command
                        logger.info(f"[Patcher] Falling back to patch command for {file_path}")
                        result = self._apply_patch_subprocess(file_path, unified_diff, repo_path)
                        if result["success"]:
                            applied.append({"file": file_path, "method": "subprocess"})
                        else:
                            failed.append({"file": file_path, "error": result["error"]})

            except Exception as e:
                logger.error(f"[Patcher] Error applying patch to {file_path}: {e}")
                failed.append({"file": file_path, "error": str(e)})

        logger.info(f"[Patcher] Applied {len(applied)}/{len(patches)} patches, {len(failed)} failed")

        return AgentResult(
            success=len(applied) > 0 or len(failed) == 0,
            agent_name=self.name,
            action="apply_all_patches",
            data={
                "applied": len(applied),
                "failed": len(failed),
                "applied_files": applied,
                "failed_files": failed,
            },
            warnings=[f"Failed to apply {len(failed)} patches"] if failed else [],
        )

    def _apply_unified_diff(self, original: str, diff: str) -> str | None:
        """Apply a unified diff to original content. Returns None if it can't be applied."""
        import re

        lines = original.splitlines(keepends=True)
        diff_lines = diff.splitlines()

        # Parse hunks from the diff
        hunks = []
        current_hunk = None

        for line in diff_lines:
            if line.startswith('@@'):
                # Parse hunk header: @@ -start,count +start,count @@
                match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
                if match:
                    if current_hunk:
                        hunks.append(current_hunk)
                    current_hunk = {
                        'old_start': int(match.group(1)),
                        'old_count': int(match.group(2) or 1),
                        'new_start': int(match.group(3)),
                        'new_count': int(match.group(4) or 1),
                        'lines': []
                    }
            elif current_hunk is not None:
                if line.startswith('+') or line.startswith('-') or line.startswith(' '):
                    current_hunk['lines'].append(line)

        if current_hunk:
            hunks.append(current_hunk)

        if not hunks:
            logger.warning("[Patcher] No hunks found in diff")
            return None

        # Apply hunks in reverse order to preserve line numbers
        result_lines = lines[:]
        offset = 0

        try:
            for hunk in hunks:
                start_idx = hunk['old_start'] - 1 + offset

                # Build replacement lines
                new_lines = []
                for hunk_line in hunk['lines']:
                    if hunk_line.startswith('+'):
                        new_lines.append(hunk_line[1:] + '\n' if not hunk_line[1:].endswith('\n') else hunk_line[1:])
                    elif hunk_line.startswith(' '):
                        new_lines.append(hunk_line[1:] + '\n' if not hunk_line[1:].endswith('\n') else hunk_line[1:])
                    # Lines starting with '-' are removed (not added to new_lines)

                # Replace the old lines with new lines
                old_line_count = sum(1 for l in hunk['lines'] if l.startswith('-') or l.startswith(' '))
                result_lines[start_idx:start_idx + old_line_count] = new_lines

                # Update offset for next hunk
                offset += len(new_lines) - old_line_count

            return ''.join(result_lines)
        except Exception as e:
            logger.warning(f"[Patcher] Failed to apply diff manually: {e}")
            return None

    def _apply_patch_subprocess(self, file_path: str, unified_diff: str, repo_path: Path) -> dict:
        """Apply patch using subprocess as fallback."""
        import subprocess
        import tempfile
        import os

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as f:
                f.write(unified_diff)
                patch_file = f.name

            result = subprocess.run(
                ["patch", "-p0", "-f", "-s", "-i", patch_file],
                capture_output=True,
                text=True,
                cwd=repo_path if repo_path.exists() else Path(file_path).parent,
                timeout=30,
            )

            try:
                os.unlink(patch_file)
            except Exception:
                pass

            if result.returncode == 0:
                return {"success": True}
            else:
                return {"success": False, "error": result.stderr or result.stdout or "Patch command failed"}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Patch timed out"}
        except FileNotFoundError:
            return {"success": False, "error": "patch command not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _create_pr(self, context: AgentContext, **kwargs) -> AgentResult:
        """Create a git branch with patches, optionally push and create PR."""
        import subprocess
        from datetime import datetime

        logger.info("[Patcher] Starting create_pr action")

        repo_path = Path(kwargs.get("repository_path", ""))
        patches = kwargs.get("patches", [])

        logger.info(f"[Patcher] Repository: {repo_path}, Patches: {len(patches)}")
        from_version = kwargs.get("from_version", "")
        to_version = kwargs.get("to_version", "")
        branch_name = kwargs.get("branch_name", "")
        push = kwargs.get("push", False)
        create_remote_pr = kwargs.get("create_remote_pr", False)
        run_tests_first = kwargs.get("run_tests_first", False)
        pr_title = kwargs.get("pr_title", "")
        pr_body = kwargs.get("pr_body", "")

        if not repo_path.exists():
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="create_pr",
                error=f"Repository path does not exist: {repo_path}",
            )

        # Generate branch name if not provided
        if not branch_name:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            branch_name = f"jdk-upgrade/{from_version}-to-{to_version}/{timestamp}"

        # Generate PR title if not provided
        if not pr_title:
            pr_title = f"chore: JDK upgrade from {from_version} to {to_version}"

        # Generate PR body if not provided
        if not pr_body:
            pr_body = f"""## JDK Upgrade: {from_version} → {to_version}

This PR contains automated compatibility fixes for upgrading from JDK {from_version} to {to_version}.

### Changes
- Applied {len(patches)} patches to fix JDK compatibility issues
- Automated by JavaPatching tool

### Testing
Please run the test suite to verify the changes.
"""

        try:
            # Check if git repo
            logger.info("[Patcher] Checking git status...")
            result = subprocess.run(
                ["git", "status"],
                capture_output=True,
                text=True,
                cwd=repo_path,
                timeout=10,
            )
            if result.returncode != 0:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    action="create_pr",
                    error="Not a git repository",
                )

            # Detect remote type (github, bitbucket, gitlab)
            logger.info("[Patcher] Detecting remote type...")
            remote_url = ""
            remote_type = "unknown"
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                cwd=repo_path,
                timeout=10,
            )
            if result.returncode == 0:
                remote_url = result.stdout.strip()
                if "github.com" in remote_url:
                    remote_type = "github"
                elif "bitbucket" in remote_url:
                    remote_type = "bitbucket"
                elif "gitlab" in remote_url:
                    remote_type = "gitlab"
            logger.info(f"[Patcher] Remote: {remote_type} ({remote_url})")

            # Create and checkout new branch
            logger.info(f"[Patcher] Creating branch: {branch_name}")
            result = subprocess.run(
                ["git", "checkout", "-b", branch_name],
                capture_output=True,
                text=True,
                cwd=repo_path,
                timeout=10,
            )
            if result.returncode != 0:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    action="create_pr",
                    error=f"Failed to create branch: {result.stderr}",
                )
            logger.info(f"[Patcher] Branch created successfully")

            # Apply patches
            logger.info(f"[Patcher] Applying {len(patches)} patches...")
            apply_result = await self._apply_all_patches(context, **kwargs)
            logger.info(f"[Patcher] Patch application result: success={apply_result.success}")
            if not apply_result.success:
                # Cleanup: go back to previous branch
                logger.warning("[Patcher] Patches failed, cleaning up branch")
                subprocess.run(["git", "checkout", "-"], cwd=repo_path, timeout=10)
                subprocess.run(["git", "branch", "-D", branch_name], cwd=repo_path, timeout=10)
                return apply_result

            # Stage all changes
            logger.info("[Patcher] Staging changes...")
            result = subprocess.run(
                ["git", "add", "-A"],
                capture_output=True,
                text=True,
                cwd=repo_path,
                timeout=30,
            )

            # Commit
            logger.info("[Patcher] Committing changes...")
            commit_msg = f"chore: JDK upgrade from {from_version} to {to_version}\n\nAutomated JDK compatibility fixes applied by JavaPatching tool."
            result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                capture_output=True,
                text=True,
                cwd=repo_path,
                timeout=30,
            )
            if result.returncode != 0:
                logger.warning(f"[Patcher] Commit failed: {result.stderr}")
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    action="create_pr",
                    error=f"Failed to commit: {result.stderr}",
                )

            # Get commit hash
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=repo_path,
            )
            commit_hash = result.stdout.strip() if result.returncode == 0 else "unknown"

            # Run tests if requested
            test_result = None
            if run_tests_first:
                logger.info("[Patcher] Running tests before PR...")
                test_result = await self._run_tests(context, repository_path=repo_path)
                if not test_result.success or not test_result.data.get("tests_passed", False):
                    # Tests failed - cleanup and return error
                    logger.warning("[Patcher] Tests failed, aborting PR creation")
                    subprocess.run(["git", "checkout", "-"], cwd=repo_path, timeout=10)
                    subprocess.run(["git", "branch", "-D", branch_name], cwd=repo_path, timeout=10)
                    return AgentResult(
                        success=False,
                        agent_name=self.name,
                        action="create_pr",
                        error="Tests failed - PR not created",
                        data={
                            "test_result": test_result.data if test_result else None,
                            "branch_deleted": True,
                        },
                    )
                logger.info("[Patcher] Tests passed!")

            response_data = {
                "branch_name": branch_name,
                "commit_hash": commit_hash,
                "files_changed": apply_result.data.get("applied", 0),
                "remote_type": remote_type,
                "remote_url": remote_url,
                "tests_ran": run_tests_first,
                "tests_passed": test_result.data.get("tests_passed", False) if test_result else None,
                "test_summary": {
                    "tests_run": test_result.data.get("tests_run", 0),
                    "failures": test_result.data.get("failures", 0),
                    "errors": test_result.data.get("errors", 0),
                } if test_result else None,
            }

            # Push to remote if requested
            if push:
                logger.info(f"[Patcher] Pushing branch {branch_name} to origin")
                result = subprocess.run(
                    ["git", "push", "-u", "origin", branch_name],
                    capture_output=True,
                    text=True,
                    cwd=repo_path,
                )
                if result.returncode != 0:
                    response_data["push_error"] = result.stderr
                    response_data["message"] = f"Branch created but push failed: {result.stderr}"
                    return AgentResult(
                        success=True,
                        agent_name=self.name,
                        action="create_pr",
                        data=response_data,
                        warnings=[f"Push failed: {result.stderr}"],
                    )
                response_data["pushed"] = True

                # Create PR if requested
                if create_remote_pr:
                    pr_result = await self._create_remote_pr(
                        repo_path, branch_name, pr_title, pr_body, remote_type
                    )
                    response_data["pr_result"] = pr_result

            if not push:
                response_data["message"] = f"Branch '{branch_name}' created. Push with: git push -u origin {branch_name}"
                response_data["next_steps"] = [
                    f"git push -u origin {branch_name}",
                    f"Create PR on {remote_type}" if remote_type != "unknown" else "Create PR on your git platform",
                ]
            elif not create_remote_pr:
                response_data["message"] = f"Branch '{branch_name}' pushed to origin. Create PR manually."
            else:
                # Check if PR was created successfully or if we have a manual URL
                pr_result = response_data.get("pr_result", {})
                if pr_result.get("success"):
                    response_data["message"] = "Branch pushed and PR created successfully."
                elif pr_result.get("manual_pr_url"):
                    response_data["message"] = f"Branch pushed. Create PR here: {pr_result['manual_pr_url']}"
                    response_data["pr_url"] = pr_result["manual_pr_url"]
                else:
                    response_data["message"] = f"Branch pushed but PR creation failed: {pr_result.get('error', 'Unknown error')}"

            return AgentResult(
                success=True,
                agent_name=self.name,
                action="create_pr",
                data=response_data,
            )

        except Exception as e:
            logger.error(f"[Patcher] create_pr failed: {e}")
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="create_pr",
                error=str(e),
            )

    async def _create_remote_pr(
        self,
        repo_path: Path,
        branch_name: str,
        title: str,
        body: str,
        remote_type: str,
    ) -> dict:
        """Create a PR on the remote platform (GitHub, Bitbucket, GitLab)."""
        import subprocess

        if remote_type == "github":
            # Get the remote URL to construct manual PR link
            import re
            remote_result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                cwd=repo_path,
            )
            remote_url = remote_result.stdout.strip() if remote_result.returncode == 0 else ""

            # Parse GitHub owner/repo from remote URL
            # Handles: git@github.com:owner/repo.git or https://github.com/owner/repo.git
            github_match = re.search(r'github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$', remote_url)
            if github_match:
                owner, repo = github_match.group(1), github_match.group(2)
                manual_pr_url = f"https://github.com/{owner}/{repo}/compare/main...{branch_name}?expand=1"
            else:
                manual_pr_url = None

            # Try GitHub CLI (gh) first
            try:
                result = subprocess.run(
                    ["gh", "pr", "create", "--title", title, "--body", body, "--head", branch_name],
                    capture_output=True,
                    text=True,
                    cwd=repo_path,
                )
                if result.returncode == 0:
                    pr_url = result.stdout.strip()
                    return {"success": True, "pr_url": pr_url}
                else:
                    return {
                        "success": False,
                        "error": result.stderr,
                        "manual_pr_url": manual_pr_url,
                    }
            except FileNotFoundError:
                return {
                    "success": False,
                    "error": "GitHub CLI (gh) not installed",
                    "manual_pr_url": manual_pr_url,
                    "instructions": "Install gh CLI with: brew install gh && gh auth login",
                }

        elif remote_type == "bitbucket":
            # For Bitbucket, we need to use the API or bb CLI
            # Try bb CLI first, fall back to API instructions
            try:
                result = subprocess.run(
                    ["bb", "pr", "create", "--title", title, "--description", body, "--source", branch_name],
                    capture_output=True,
                    text=True,
                    cwd=repo_path,
                )
                if result.returncode == 0:
                    return {"success": True, "output": result.stdout.strip()}
                else:
                    return {"success": False, "error": result.stderr}
            except FileNotFoundError:
                # Return instructions for manual PR or API
                return {
                    "success": False,
                    "error": "Bitbucket CLI not found",
                    "instructions": [
                        "Option 1: Install Bitbucket CLI: pip install bitbucket-cli",
                        "Option 2: Create PR manually in Bitbucket UI",
                        "Option 3: Use Bitbucket API with curl:",
                        f"  Set BITBUCKET_USERNAME and BITBUCKET_APP_PASSWORD environment variables",
                    ],
                }

        elif remote_type == "gitlab":
            # Use GitLab CLI (glab)
            try:
                result = subprocess.run(
                    ["glab", "mr", "create", "--title", title, "--description", body, "--source-branch", branch_name],
                    capture_output=True,
                    text=True,
                    cwd=repo_path,
                )
                if result.returncode == 0:
                    return {"success": True, "output": result.stdout.strip()}
                else:
                    return {"success": False, "error": result.stderr}
            except FileNotFoundError:
                return {
                    "success": False,
                    "error": "GitLab CLI (glab) not installed. Install with: brew install glab",
                }

        else:
            return {
                "success": False,
                "error": f"Unknown remote type: {remote_type}. Create PR manually.",
            }

    async def _run_tests(self, context: AgentContext, **kwargs) -> AgentResult:
        """Run Maven or Gradle tests in the repository."""
        import subprocess
        import shutil

        repo_path = kwargs.get("repository_path", "")
        if isinstance(repo_path, str):
            repo_path = Path(repo_path)

        logger.info(f"[Patcher] _run_tests called with repo_path: {repo_path}")

        if not repo_path or not repo_path.exists():
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="run_tests",
                error=f"Repository path does not exist: {repo_path}",
            )

        # Detect build tool
        pom_path = repo_path / "pom.xml"
        gradle_path = repo_path / "build.gradle"
        gradle_kts_path = repo_path / "build.gradle.kts"
        gradlew_path = repo_path / "gradlew"

        logger.info(f"[Patcher] Checking build files - pom.xml: {pom_path.exists()}, build.gradle: {gradle_path.exists()}")

        try:
            if pom_path.exists():
                # Maven project - check if mvn is available
                mvn_path = shutil.which("mvn")
                if not mvn_path:
                    return AgentResult(
                        success=False,
                        agent_name=self.name,
                        action="run_tests",
                        error="Maven (mvn) not found in PATH. Install Maven or add it to PATH.",
                    )

                logger.info(f"[Patcher] Running Maven tests in {repo_path} using {mvn_path}")
                result = subprocess.run(
                    ["mvn", "test", "-B", "--fail-at-end"],
                    capture_output=True,
                    text=True,
                    cwd=repo_path,
                    timeout=600,  # 10 minute timeout
                )
                build_tool = "maven"
                logger.info(f"[Patcher] Maven returned code: {result.returncode}")

            elif gradle_path.exists() or gradle_kts_path.exists():
                # Gradle project
                if gradlew_path.exists():
                    gradle_cmd = ["./gradlew"]
                    logger.info(f"[Patcher] Using gradlew wrapper")
                else:
                    gradle_path_cmd = shutil.which("gradle")
                    if not gradle_path_cmd:
                        return AgentResult(
                            success=False,
                            agent_name=self.name,
                            action="run_tests",
                            error="Gradle not found in PATH and no gradlew wrapper exists.",
                        )
                    gradle_cmd = ["gradle"]

                logger.info(f"[Patcher] Running Gradle tests in {repo_path}")
                result = subprocess.run(
                    gradle_cmd + ["test", "--no-daemon"],
                    capture_output=True,
                    text=True,
                    cwd=repo_path,
                    timeout=600,
                )
                build_tool = "gradle"
                logger.info(f"[Patcher] Gradle returned code: {result.returncode}")

            else:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    action="run_tests",
                    error="No pom.xml or build.gradle found - not a recognized Java project",
                )

            # Parse test results
            output = result.stdout + "\n" + result.stderr
            tests_passed = result.returncode == 0

            # Extract test summary (simplified)
            tests_run = 0
            failures = 0
            errors = 0

            import re
            if build_tool == "maven":
                # Maven: Tests run: X, Failures: Y, Errors: Z
                match = re.search(r"Tests run: (\d+), Failures: (\d+), Errors: (\d+)", output)
                if match:
                    tests_run = int(match.group(1))
                    failures = int(match.group(2))
                    errors = int(match.group(3))
                # Also check for "BUILD SUCCESS" or "BUILD FAILURE"
                if "BUILD SUCCESS" in output:
                    tests_passed = True
                elif "BUILD FAILURE" in output:
                    tests_passed = False
            else:
                # Gradle: X tests completed, Y failed
                match = re.search(r"(\d+) tests completed, (\d+) failed", output)
                if match:
                    tests_run = int(match.group(1))
                    failures = int(match.group(2))
                # Check for "BUILD SUCCESSFUL" or "BUILD FAILED"
                if "BUILD SUCCESSFUL" in output:
                    tests_passed = True
                elif "BUILD FAILED" in output:
                    tests_passed = False

            logger.info(f"[Patcher] Tests completed: passed={tests_passed}, run={tests_run}, failures={failures}, errors={errors}")

            # Return success=True if the action completed (even if tests failed)
            # The tests_passed field indicates whether tests actually passed
            return AgentResult(
                success=True,  # Action completed successfully
                agent_name=self.name,
                action="run_tests",
                data={
                    "build_tool": build_tool,
                    "tests_passed": tests_passed,
                    "tests_run": tests_run,
                    "failures": failures,
                    "errors": errors,
                    "return_code": result.returncode,
                    "output": output[-5000:] if len(output) > 5000 else output,  # Truncate long output
                },
                error=None if tests_passed else f"Tests failed: {failures} failures, {errors} errors",
                warnings=[] if tests_passed else [f"{failures + errors} test(s) failed"],
            )

        except subprocess.TimeoutExpired:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="run_tests",
                error="Test execution timed out after 10 minutes",
            )
        except FileNotFoundError as e:
            logger.error(f"[Patcher] Build tool not found: {e}")
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="run_tests",
                error=f"Build tool not found: {e}. Make sure Maven or Gradle is installed and in PATH.",
            )
        except Exception as e:
            logger.error(f"[Patcher] run_tests failed with exception: {e}", exc_info=True)
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="run_tests",
                error=str(e) or "Unknown error occurred",
            )

    async def health_check(self) -> bool:
        """Check if patcher agent is healthy."""
        return bool(llm_service.available_providers)
