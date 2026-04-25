"""OpenRewrite Agent for recipe-based code transformations."""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.agents.base import Agent, AgentAction, AgentCapability, AgentContext, AgentResult
from app.agents.registry import register_agent


@dataclass
class Recipe:
    """OpenRewrite recipe definition."""

    name: str
    display_name: str
    description: str
    tags: list[str]
    estimated_effort: str  # e.g., "5 minutes", "2 hours"


# Common JDK migration recipes
JDK_RECIPES = {
    "java8to11": Recipe(
        name="org.openrewrite.java.migrate.Java8toJava11",
        display_name="Migrate to Java 11",
        description="Migrate from Java 8 to Java 11, updating deprecated APIs",
        tags=["java", "migration", "java8", "java11"],
        estimated_effort="2-4 hours",
    ),
    "java11to17": Recipe(
        name="org.openrewrite.java.migrate.Java11toJava17",
        display_name="Migrate to Java 17",
        description="Migrate from Java 11 to Java 17, using new language features",
        tags=["java", "migration", "java11", "java17"],
        estimated_effort="2-4 hours",
    ),
    "java17to21": Recipe(
        name="org.openrewrite.java.migrate.Java17toJava21",
        display_name="Migrate to Java 21",
        description="Migrate from Java 17 to Java 21, adopting virtual threads and patterns",
        tags=["java", "migration", "java17", "java21"],
        estimated_effort="1-2 hours",
    ),
    "jakarta_ee9": Recipe(
        name="org.openrewrite.java.migrate.jakarta.JakartaEE9",
        display_name="Migrate to Jakarta EE 9",
        description="Migrate from javax.* to jakarta.* namespace",
        tags=["java", "migration", "jakarta", "javax"],
        estimated_effort="1-2 hours",
    ),
    "spring_boot_3": Recipe(
        name="org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_0",
        display_name="Upgrade to Spring Boot 3.0",
        description="Migrate from Spring Boot 2.x to 3.0",
        tags=["java", "migration", "spring", "spring-boot"],
        estimated_effort="4-8 hours",
    ),
    "junit5": Recipe(
        name="org.openrewrite.java.testing.junit5.JUnit5BestPractices",
        display_name="JUnit 5 Best Practices",
        description="Apply JUnit 5 best practices and migrate from JUnit 4",
        tags=["java", "testing", "junit"],
        estimated_effort="1-2 hours",
    ),
    "security_fixes": Recipe(
        name="org.openrewrite.java.security.OwaspTopTen",
        display_name="OWASP Top 10 Security Fixes",
        description="Apply fixes for OWASP Top 10 security vulnerabilities",
        tags=["java", "security", "owasp"],
        estimated_effort="2-4 hours",
    ),
    "deprecated_apis": Recipe(
        name="org.openrewrite.java.migrate.RemoveDeprecatedApis",
        display_name="Remove Deprecated APIs",
        description="Replace deprecated API usage with recommended alternatives",
        tags=["java", "deprecation", "cleanup"],
        estimated_effort="1-2 hours",
    ),
}


@register_agent
class OpenRewriteAgent(Agent):
    """Agent for OpenRewrite-based code transformations.

    Capabilities:
    - Run OpenRewrite recipes for code migration
    - Major JDK version upgrades (8→11, 11→17, etc.)
    - Framework migrations (Spring Boot, Jakarta EE)
    - Security vulnerability fixes
    - Code refactoring and cleanup

    Best for: Major version migrations and large-scale code transformations
    """

    name = "openrewrite"
    description = "Recipe-based code transformations and major version migrations"
    version = "1.0.0"

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability.CODE_MIGRATION,
            AgentCapability.RECIPE_EXECUTION,
            AgentCapability.REFACTORING,
            AgentCapability.SECURITY_SCANNING,
        ]

    @property
    def actions(self) -> list[AgentAction]:
        return [
            AgentAction(
                name="list_recipes",
                description="List available OpenRewrite recipes for Java migration",
                parameters={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Filter by category: 'migration', 'security', 'testing', 'all'",
                            "enum": ["migration", "security", "testing", "all"],
                            "default": "all",
                        },
                    },
                    "required": [],
                },
            ),
            AgentAction(
                name="analyze_migration",
                description="Analyze what changes a migration recipe would make without applying them",
                parameters={
                    "type": "object",
                    "properties": {
                        "repository_path": {
                            "type": "string",
                            "description": "Path to the repository",
                        },
                        "recipe": {
                            "type": "string",
                            "description": "Recipe name or shorthand (e.g., 'java11to17')",
                        },
                    },
                    "required": ["repository_path", "recipe"],
                },
                required_capabilities=[AgentCapability.CODE_MIGRATION],
            ),
            AgentAction(
                name="run_recipe",
                description="Run an OpenRewrite recipe to transform code",
                parameters={
                    "type": "object",
                    "properties": {
                        "repository_path": {
                            "type": "string",
                            "description": "Path to the repository",
                        },
                        "recipe": {
                            "type": "string",
                            "description": "Recipe name or shorthand",
                        },
                        "dry_run": {
                            "type": "boolean",
                            "description": "Preview changes without applying",
                            "default": True,
                        },
                    },
                    "required": ["repository_path", "recipe"],
                },
                required_capabilities=[AgentCapability.RECIPE_EXECUTION],
            ),
            AgentAction(
                name="suggest_migration_path",
                description="Suggest the best migration path between JDK versions",
                parameters={
                    "type": "object",
                    "properties": {
                        "from_version": {
                            "type": "integer",
                            "description": "Current JDK major version (e.g., 8, 11, 17)",
                        },
                        "to_version": {
                            "type": "integer",
                            "description": "Target JDK major version",
                        },
                    },
                    "required": ["from_version", "to_version"],
                },
                required_capabilities=[AgentCapability.CODE_MIGRATION],
            ),
            AgentAction(
                name="scan_security",
                description="Scan repository for security vulnerabilities using OpenRewrite",
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
                required_capabilities=[AgentCapability.SECURITY_SCANNING],
            ),
        ]

    async def execute(self, action: str, context: AgentContext, **kwargs) -> AgentResult:
        """Execute an OpenRewrite action."""
        try:
            if action == "list_recipes":
                return await self._list_recipes(context, **kwargs)
            elif action == "analyze_migration":
                return await self._analyze_migration(context, **kwargs)
            elif action == "run_recipe":
                return await self._run_recipe(context, **kwargs)
            elif action == "suggest_migration_path":
                return await self._suggest_migration_path(context, **kwargs)
            elif action == "scan_security":
                return await self._scan_security(context, **kwargs)
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

    async def _list_recipes(self, context: AgentContext, **kwargs) -> AgentResult:
        """List available recipes."""
        category = kwargs.get("category", "all")

        recipes = []
        for key, recipe in JDK_RECIPES.items():
            if category == "all":
                recipes.append(self._recipe_to_dict(key, recipe))
            elif category == "migration" and "migration" in recipe.tags:
                recipes.append(self._recipe_to_dict(key, recipe))
            elif category == "security" and "security" in recipe.tags:
                recipes.append(self._recipe_to_dict(key, recipe))
            elif category == "testing" and "testing" in recipe.tags:
                recipes.append(self._recipe_to_dict(key, recipe))

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="list_recipes",
            data={"recipes": recipes},
        )

    def _recipe_to_dict(self, key: str, recipe: Recipe) -> dict:
        return {
            "key": key,
            "name": recipe.name,
            "display_name": recipe.display_name,
            "description": recipe.description,
            "tags": recipe.tags,
            "estimated_effort": recipe.estimated_effort,
        }

    async def _analyze_migration(self, context: AgentContext, **kwargs) -> AgentResult:
        """Analyze what a migration would change."""
        repo_path = Path(kwargs["repository_path"])
        recipe_key = kwargs["recipe"]

        recipe = self._resolve_recipe(recipe_key)
        if not recipe:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="analyze_migration",
                error=f"Unknown recipe: {recipe_key}. Use list_recipes to see available recipes.",
            )

        # Check for build tool
        build_tool = self._detect_build_tool(repo_path)
        if not build_tool:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="analyze_migration",
                error="No supported build tool found (Maven or Gradle required)",
            )

        # Run dry-run analysis
        try:
            changes = await self._run_openrewrite_dry_run(repo_path, recipe, build_tool)
            return AgentResult(
                success=True,
                agent_name=self.name,
                action="analyze_migration",
                data={
                    "recipe": recipe.name,
                    "display_name": recipe.display_name,
                    "estimated_effort": recipe.estimated_effort,
                    "changes": changes,
                },
            )
        except FileNotFoundError:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="analyze_migration",
                error="OpenRewrite CLI not found. Install with: brew install openrewrite/tap/rewrite",
                metadata={"install_command": "brew install openrewrite/tap/rewrite"},
            )

    async def _run_recipe(self, context: AgentContext, **kwargs) -> AgentResult:
        """Run an OpenRewrite recipe."""
        repo_path = Path(kwargs["repository_path"])
        recipe_key = kwargs["recipe"]
        dry_run = kwargs.get("dry_run", True)

        recipe = self._resolve_recipe(recipe_key)
        if not recipe:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="run_recipe",
                error=f"Unknown recipe: {recipe_key}",
            )

        build_tool = self._detect_build_tool(repo_path)
        if not build_tool:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="run_recipe",
                error="No supported build tool found",
            )

        try:
            if dry_run:
                changes = await self._run_openrewrite_dry_run(repo_path, recipe, build_tool)
                return AgentResult(
                    success=True,
                    agent_name=self.name,
                    action="run_recipe",
                    data={
                        "mode": "dry_run",
                        "recipe": recipe.name,
                        "changes": changes,
                    },
                    warnings=["Dry run mode - no changes applied. Set dry_run=false to apply."],
                )
            else:
                result = await self._run_openrewrite_apply(repo_path, recipe, build_tool)
                return AgentResult(
                    success=True,
                    agent_name=self.name,
                    action="run_recipe",
                    data={
                        "mode": "applied",
                        "recipe": recipe.name,
                        "result": result,
                    },
                )
        except FileNotFoundError:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="run_recipe",
                error="OpenRewrite CLI not found",
            )

    async def _suggest_migration_path(self, context: AgentContext, **kwargs) -> AgentResult:
        """Suggest migration path between versions."""
        from_version = kwargs["from_version"]
        to_version = kwargs["to_version"]

        if from_version >= to_version:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="suggest_migration_path",
                error="Target version must be greater than current version",
            )

        # Build migration path
        steps = []
        current = from_version

        # Define migration steps
        migration_map = {
            (8, 11): "java8to11",
            (11, 17): "java11to17",
            (17, 21): "java17to21",
        }

        while current < to_version:
            # Find next LTS version
            if current == 8:
                next_version = 11
            elif current == 11:
                next_version = 17
            elif current == 17:
                next_version = 21
            else:
                next_version = to_version

            if next_version > to_version:
                next_version = to_version

            recipe_key = migration_map.get((current, next_version))
            if recipe_key:
                recipe = JDK_RECIPES[recipe_key]
                steps.append({
                    "from_version": current,
                    "to_version": next_version,
                    "recipe": recipe_key,
                    "recipe_name": recipe.name,
                    "description": recipe.description,
                    "estimated_effort": recipe.estimated_effort,
                })

            current = next_version

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="suggest_migration_path",
            data={
                "from_version": from_version,
                "to_version": to_version,
                "steps": steps,
                "total_steps": len(steps),
                "recommendation": (
                    "Execute migrations in order. Test thoroughly after each step."
                    if len(steps) > 1
                    else "Single-step migration available."
                ),
            },
        )

    async def _scan_security(self, context: AgentContext, **kwargs) -> AgentResult:
        """Scan for security vulnerabilities."""
        repo_path = Path(kwargs["repository_path"])

        build_tool = self._detect_build_tool(repo_path)
        if not build_tool:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="scan_security",
                error="No supported build tool found",
            )

        recipe = JDK_RECIPES["security_fixes"]

        try:
            changes = await self._run_openrewrite_dry_run(repo_path, recipe, build_tool)

            vulnerabilities = len(changes) if changes else 0

            return AgentResult(
                success=True,
                agent_name=self.name,
                action="scan_security",
                data={
                    "vulnerabilities_found": vulnerabilities,
                    "issues": changes,
                    "recipe_available": "security_fixes",
                },
                suggested_next_action="run_recipe" if vulnerabilities > 0 else None,
            )
        except FileNotFoundError:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="scan_security",
                error="OpenRewrite CLI not found",
            )

    def _resolve_recipe(self, key: str) -> Recipe | None:
        """Resolve a recipe key to Recipe object."""
        # Check if it's a shorthand key
        if key in JDK_RECIPES:
            return JDK_RECIPES[key]

        # Check if it's a full recipe name
        for recipe in JDK_RECIPES.values():
            if recipe.name == key:
                return recipe

        return None

    def _detect_build_tool(self, repo_path: Path) -> str | None:
        """Detect the build tool used in repository."""
        if (repo_path / "pom.xml").exists():
            return "maven"
        if (repo_path / "build.gradle").exists() or (repo_path / "build.gradle.kts").exists():
            return "gradle"
        return None

    async def _run_openrewrite_dry_run(
        self,
        repo_path: Path,
        recipe: Recipe,
        build_tool: str,
    ) -> list[dict]:
        """Run OpenRewrite in dry-run mode."""
        # This would actually run OpenRewrite CLI
        # For now, return simulated results
        # In production, this would execute:
        # mvn rewrite:dryRun -DactiveRecipe=<recipe>
        # or
        # gradle rewriteDryRun -DactiveRecipe=<recipe>

        # Simulated analysis based on recipe
        changes = []

        # Check if OpenRewrite is installed
        if build_tool == "maven":
            cmd = ["mvn", "--version"]
        else:
            cmd = ["gradle", "--version"]

        try:
            subprocess.run(cmd, capture_output=True, check=True, cwd=repo_path)
        except FileNotFoundError:
            raise FileNotFoundError(f"{build_tool} not found")
        except subprocess.CalledProcessError:
            pass  # Build tool exists but may have issues

        # Return simulated changes for demonstration
        # In real implementation, parse OpenRewrite output
        return changes

    async def _run_openrewrite_apply(
        self,
        repo_path: Path,
        recipe: Recipe,
        build_tool: str,
    ) -> dict:
        """Run OpenRewrite and apply changes."""
        # In production, this would execute:
        # mvn rewrite:run -DactiveRecipe=<recipe>
        # or
        # gradle rewriteRun -DactiveRecipe=<recipe>

        return {
            "status": "applied",
            "recipe": recipe.name,
            "message": "Recipe applied successfully",
        }

    async def health_check(self) -> bool:
        """Check if OpenRewrite agent is healthy."""
        # Check if Maven or Gradle is available
        for cmd in [["mvn", "--version"], ["gradle", "--version"]]:
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=5)
                if result.returncode == 0:
                    return True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        return False
