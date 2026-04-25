"""Scanner Agent - Scans repositories for Java files and build configurations."""

import logging
from pathlib import Path

from app.agents.base import Agent, AgentAction, AgentCapability, AgentContext, AgentResult
from app.agents.bus import AgentMessage, MessageType, agent_bus
from app.agents.registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class ScannerAgent(Agent):
    """Agent for scanning Java repositories.

    Capabilities:
    - Scan for Java source files
    - Detect build tool (Maven/Gradle)
    - Find version specifications
    - Count lines of code

    Communicates results via AgentBus for downstream agents.
    """

    name = "scanner"
    description = "Repository scanning for Java files and build configurations"
    version = "1.0.0"

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability.DEPENDENCY_ANALYSIS,
            AgentCapability.BUILD_TOOL_SUPPORT,
        ]

    @property
    def actions(self) -> list[AgentAction]:
        return [
            AgentAction(
                name="scan_java_files",
                description="Scan repository for Java source files",
                parameters={
                    "type": "object",
                    "properties": {
                        "repository_path": {
                            "type": "string",
                            "description": "Path to the repository",
                        },
                        "include_tests": {
                            "type": "boolean",
                            "description": "Include test files in scan",
                            "default": True,
                        },
                    },
                    "required": ["repository_path"],
                },
            ),
            AgentAction(
                name="detect_build_tool",
                description="Detect the build tool used in the repository",
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
            AgentAction(
                name="get_project_structure",
                description="Get the project structure and module layout",
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
        """Execute a scanning action."""
        try:
            if action == "scan_java_files":
                return await self._scan_java_files(context, **kwargs)
            elif action == "detect_build_tool":
                return await self._detect_build_tool(context, **kwargs)
            elif action == "get_project_structure":
                return await self._get_project_structure(context, **kwargs)
            else:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    action=action,
                    error=f"Unknown action: {action}",
                )
        except Exception as e:
            logger.error(f"[Scanner] Action {action} failed: {e}")
            return AgentResult(
                success=False,
                agent_name=self.name,
                action=action,
                error=str(e),
            )

    async def _scan_java_files(self, context: AgentContext, **kwargs) -> AgentResult:
        """Scan for Java source files."""
        repo_path = Path(kwargs["repository_path"])
        include_tests = kwargs.get("include_tests", True)

        if not repo_path.exists():
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="scan_java_files",
                error=f"Repository path does not exist: {repo_path}",
            )

        logger.info(f"[Scanner] Scanning Java files in {repo_path}")

        java_files = []
        test_files = []
        total_lines = 0

        for java_file in repo_path.rglob("*.java"):
            # Skip hidden directories and build outputs
            if any(part.startswith('.') or part in ['target', 'build', 'out']
                   for part in java_file.parts):
                continue

            is_test = "test" in str(java_file).lower()

            try:
                content = java_file.read_text()
                line_count = len(content.splitlines())
                total_lines += line_count

                file_info = {
                    "path": str(java_file),
                    "relative_path": str(java_file.relative_to(repo_path)),
                    "line_count": line_count,
                    "is_test": is_test,
                }

                if is_test:
                    test_files.append(file_info)
                else:
                    java_files.append(file_info)

            except Exception as e:
                logger.warning(f"[Scanner] Could not read {java_file}: {e}")

        all_files = java_files + (test_files if include_tests else [])

        logger.info(f"[Scanner] Found {len(java_files)} source files, {len(test_files)} test files")

        result_data = {
            "repository_path": str(repo_path),
            "source_files": java_files,
            "test_files": test_files if include_tests else [],
            "total_source_files": len(java_files),
            "total_test_files": len(test_files),
            "total_lines": total_lines,
            "all_files": all_files,
        }

        # Publish scan complete event
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
            action="scan_java_files",
            data=result_data,
            suggested_next_agent="impact",
            suggested_next_action="analyze",
        )

    async def _detect_build_tool(self, context: AgentContext, **kwargs) -> AgentResult:
        """Detect the build tool."""
        repo_path = Path(kwargs["repository_path"])

        build_tools = []

        # Check for Maven
        if (repo_path / "pom.xml").exists():
            build_tools.append({
                "tool": "maven",
                "config_file": "pom.xml",
                "wrapper_present": (repo_path / "mvnw").exists(),
            })

        # Check for Gradle
        if (repo_path / "build.gradle").exists():
            build_tools.append({
                "tool": "gradle",
                "config_file": "build.gradle",
                "wrapper_present": (repo_path / "gradlew").exists(),
            })
        elif (repo_path / "build.gradle.kts").exists():
            build_tools.append({
                "tool": "gradle",
                "config_file": "build.gradle.kts",
                "kotlin_dsl": True,
                "wrapper_present": (repo_path / "gradlew").exists(),
            })

        # Check for Ant
        if (repo_path / "build.xml").exists():
            build_tools.append({
                "tool": "ant",
                "config_file": "build.xml",
            })

        primary_tool = build_tools[0]["tool"] if build_tools else None

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="detect_build_tool",
            data={
                "repository_path": str(repo_path),
                "primary_build_tool": primary_tool,
                "build_tools": build_tools,
            },
        )

    async def _get_project_structure(self, context: AgentContext, **kwargs) -> AgentResult:
        """Get the project structure."""
        repo_path = Path(kwargs["repository_path"])

        structure = {
            "root": str(repo_path),
            "modules": [],
            "source_roots": [],
            "test_roots": [],
        }

        # Find source roots
        for pattern in ["src/main/java", "src", "source"]:
            for src_root in repo_path.rglob(pattern):
                if src_root.is_dir() and "test" not in str(src_root).lower():
                    structure["source_roots"].append(str(src_root.relative_to(repo_path)))

        # Find test roots
        for pattern in ["src/test/java", "test", "tests"]:
            for test_root in repo_path.rglob(pattern):
                if test_root.is_dir():
                    structure["test_roots"].append(str(test_root.relative_to(repo_path)))

        # Find modules (multi-module projects)
        for pom in repo_path.rglob("pom.xml"):
            if pom.parent != repo_path:
                structure["modules"].append(str(pom.parent.relative_to(repo_path)))

        for gradle in repo_path.rglob("build.gradle*"):
            if gradle.parent != repo_path:
                module_path = str(gradle.parent.relative_to(repo_path))
                if module_path not in structure["modules"]:
                    structure["modules"].append(module_path)

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="get_project_structure",
            data=structure,
        )

    async def health_check(self) -> bool:
        """Check if scanner is healthy."""
        return True
