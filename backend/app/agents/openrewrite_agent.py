"""OpenRewrite Agent for recipe-based code transformations."""

import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from app.agents.base import Agent, AgentAction, AgentCapability, AgentContext, AgentResult
from app.agents.registry import register_agent

logger = logging.getLogger(__name__)


@dataclass
class Recipe:
    """OpenRewrite recipe definition."""

    name: str
    display_name: str
    description: str
    tags: list[str] = field(default_factory=list)
    options: list[dict] = field(default_factory=list)
    source: str = "openrewrite"  # Where this recipe came from


class RecipeService:
    """Service for fetching OpenRewrite recipes."""

    RECIPE_SOURCES = [
        # Moderne recipe catalog API
        "https://api.moderne.io/v1/recipes",
        # OpenRewrite GitHub raw recipes
        "https://raw.githubusercontent.com/openrewrite/rewrite-recipe-catalog/main/recipes.json",
    ]

    # Common JDK migration recipes (fallback if API unavailable)
    FALLBACK_RECIPES = {
        "org.openrewrite.java.migrate.Java8toJava11": {
            "name": "org.openrewrite.java.migrate.Java8toJava11",
            "displayName": "Migrate to Java 11",
            "description": "Migrate from Java 8 to Java 11, updating deprecated APIs",
            "tags": ["java", "migration", "java8", "java11"],
        },
        "org.openrewrite.java.migrate.UpgradeToJava11": {
            "name": "org.openrewrite.java.migrate.UpgradeToJava11",
            "displayName": "Upgrade to Java 11",
            "description": "Migrate to Java 11 from any earlier version",
            "tags": ["java", "migration", "java11"],
        },
        "org.openrewrite.java.migrate.UpgradeToJava17": {
            "name": "org.openrewrite.java.migrate.UpgradeToJava17",
            "displayName": "Upgrade to Java 17",
            "description": "Migrate to Java 17 from any earlier version",
            "tags": ["java", "migration", "java17"],
        },
        "org.openrewrite.java.migrate.UpgradeToJava21": {
            "name": "org.openrewrite.java.migrate.UpgradeToJava21",
            "displayName": "Upgrade to Java 21",
            "description": "Migrate to Java 21 from any earlier version",
            "tags": ["java", "migration", "java21"],
        },
        "org.openrewrite.java.migrate.jakarta.JakartaEE10": {
            "name": "org.openrewrite.java.migrate.jakarta.JakartaEE10",
            "displayName": "Migrate to Jakarta EE 10",
            "description": "Migrate from javax.* to jakarta.* namespace",
            "tags": ["java", "migration", "jakarta"],
        },
        "org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_3": {
            "name": "org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_3",
            "displayName": "Upgrade to Spring Boot 3.3",
            "description": "Migrate to Spring Boot 3.3",
            "tags": ["java", "spring", "spring-boot"],
        },
        "org.openrewrite.java.security.OwaspA01": {
            "name": "org.openrewrite.java.security.OwaspA01",
            "displayName": "OWASP A01:2021 Broken Access Control",
            "description": "Fix broken access control vulnerabilities",
            "tags": ["java", "security", "owasp"],
        },
    }

    def __init__(self):
        self._cache: dict[str, Recipe] = {}
        self._cache_loaded = False

    async def fetch_recipes(self, category: str | None = None) -> list[Recipe]:
        """Fetch recipes from OpenRewrite sources."""
        if not self._cache_loaded:
            await self._load_recipes()

        recipes = list(self._cache.values())

        if category:
            recipes = [r for r in recipes if category.lower() in [t.lower() for t in r.tags]]

        return recipes

    async def get_recipe(self, name: str) -> Recipe | None:
        """Get a specific recipe by name."""
        if not self._cache_loaded:
            await self._load_recipes()

        return self._cache.get(name)

    async def search_recipes(self, query: str) -> list[Recipe]:
        """Search recipes by name or description."""
        if not self._cache_loaded:
            await self._load_recipes()

        query_lower = query.lower()
        return [
            r for r in self._cache.values()
            if query_lower in r.name.lower()
            or query_lower in r.display_name.lower()
            or query_lower in r.description.lower()
        ]

    async def _load_recipes(self):
        """Load recipes from API or fallback."""
        logger.info("[OpenRewrite] Loading recipes...")

        # Try to fetch from Moderne API
        recipes = await self._fetch_from_moderne()

        if not recipes:
            # Try OpenRewrite docs
            recipes = await self._fetch_from_docs()

        if not recipes:
            # Use fallback
            logger.warning("[OpenRewrite] Using fallback recipes")
            recipes = self._get_fallback_recipes()

        for recipe in recipes:
            self._cache[recipe.name] = recipe

        self._cache_loaded = True
        logger.info(f"[OpenRewrite] Loaded {len(self._cache)} recipes")

    async def _fetch_from_moderne(self) -> list[Recipe]:
        """Fetch recipes from Moderne API."""
        recipes = []
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Moderne's public recipe search endpoint
                resp = await client.get(
                    "https://app.moderne.io/api/v1/recipes/search",
                    params={"q": "java migrate", "limit": 100},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("recipes", []):
                        recipes.append(Recipe(
                            name=item.get("id", ""),
                            display_name=item.get("name", ""),
                            description=item.get("description", ""),
                            tags=item.get("tags", []),
                            options=item.get("options", []),
                            source="moderne",
                        ))
                    logger.info(f"[OpenRewrite] Fetched {len(recipes)} from Moderne")
        except Exception as e:
            logger.warning(f"[OpenRewrite] Moderne API failed: {e}")

        return recipes

    async def _fetch_from_docs(self) -> list[Recipe]:
        """Fetch recipes from OpenRewrite docs."""
        recipes = []
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # OpenRewrite recipe catalog
                resp = await client.get(
                    "https://docs.openrewrite.org/recipes/java/migrate"
                )
                if resp.status_code == 200:
                    # Parse the docs page for recipe info
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "html.parser")

                    for link in soup.find_all("a", href=True):
                        href = link.get("href", "")
                        if "/recipes/" in href and "java" in href:
                            name = link.get_text().strip()
                            if name:
                                # Extract recipe name from URL
                                recipe_name = href.split("/")[-1].replace("-", ".")
                                if recipe_name.startswith("org."):
                                    recipes.append(Recipe(
                                        name=recipe_name,
                                        display_name=name,
                                        description=f"OpenRewrite recipe: {name}",
                                        tags=["java", "migration"],
                                        source="docs",
                                    ))
                    logger.info(f"[OpenRewrite] Fetched {len(recipes)} from docs")
        except Exception as e:
            logger.warning(f"[OpenRewrite] Docs fetch failed: {e}")

        return recipes

    def _get_fallback_recipes(self) -> list[Recipe]:
        """Get fallback recipes."""
        return [
            Recipe(
                name=data["name"],
                display_name=data["displayName"],
                description=data["description"],
                tags=data.get("tags", []),
                source="fallback",
            )
            for data in self.FALLBACK_RECIPES.values()
        ]


# Global recipe service
recipe_service = RecipeService()


@register_agent
class OpenRewriteAgent(Agent):
    """Agent for OpenRewrite-based code transformations.

    Capabilities:
    - Fetch available recipes from OpenRewrite/Moderne
    - Run OpenRewrite recipes for code migration
    - Major JDK version upgrades (8→11, 11→17, etc.)
    - Framework migrations (Spring Boot, Jakarta EE)
    - Security vulnerability fixes

    Best for: Major version migrations and large-scale code transformations
    """

    name = "openrewrite"
    description = "Recipe-based code transformations and major version migrations"
    version = "2.0.0"

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
                description="List available OpenRewrite recipes (fetched from API)",
                parameters={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Filter by category: 'migration', 'security', 'spring', 'testing'",
                        },
                        "search": {
                            "type": "string",
                            "description": "Search query for recipes",
                        },
                    },
                    "required": [],
                },
            ),
            AgentAction(
                name="get_recipe",
                description="Get details for a specific recipe",
                parameters={
                    "type": "object",
                    "properties": {
                        "recipe_name": {
                            "type": "string",
                            "description": "Full recipe name (e.g., 'org.openrewrite.java.migrate.UpgradeToJava17')",
                        },
                    },
                    "required": ["recipe_name"],
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
                            "description": "Recipe name (e.g., 'org.openrewrite.java.migrate.UpgradeToJava17')",
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
                            "description": "Recipe name",
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
        ]

    async def execute(self, action: str, context: AgentContext, **kwargs) -> AgentResult:
        """Execute an OpenRewrite action."""
        try:
            if action == "list_recipes":
                return await self._list_recipes(context, **kwargs)
            elif action == "get_recipe":
                return await self._get_recipe(context, **kwargs)
            elif action == "analyze_migration":
                return await self._analyze_migration(context, **kwargs)
            elif action == "run_recipe":
                return await self._run_recipe(context, **kwargs)
            elif action == "suggest_migration_path":
                return await self._suggest_migration_path(context, **kwargs)
            else:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    action=action,
                    error=f"Unknown action: {action}",
                )
        except Exception as e:
            logger.error(f"[OpenRewrite] Action {action} failed: {e}")
            return AgentResult(
                success=False,
                agent_name=self.name,
                action=action,
                error=str(e),
            )

    async def _list_recipes(self, context: AgentContext, **kwargs) -> AgentResult:
        """List available recipes."""
        category = kwargs.get("category")
        search = kwargs.get("search")

        if search:
            recipes = await recipe_service.search_recipes(search)
        else:
            recipes = await recipe_service.fetch_recipes(category)

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="list_recipes",
            data={
                "total": len(recipes),
                "recipes": [
                    {
                        "name": r.name,
                        "display_name": r.display_name,
                        "description": r.description,
                        "tags": r.tags,
                        "source": r.source,
                    }
                    for r in recipes
                ],
            },
        )

    async def _get_recipe(self, context: AgentContext, **kwargs) -> AgentResult:
        """Get details for a specific recipe."""
        recipe_name = kwargs["recipe_name"]

        recipe = await recipe_service.get_recipe(recipe_name)

        if not recipe:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="get_recipe",
                error=f"Recipe not found: {recipe_name}",
            )

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="get_recipe",
            data={
                "name": recipe.name,
                "display_name": recipe.display_name,
                "description": recipe.description,
                "tags": recipe.tags,
                "options": recipe.options,
                "source": recipe.source,
            },
        )

    async def _analyze_migration(self, context: AgentContext, **kwargs) -> AgentResult:
        """Analyze what a migration would change."""
        repo_path = Path(kwargs["repository_path"])
        recipe_name = kwargs["recipe"]

        recipe = await recipe_service.get_recipe(recipe_name)
        if not recipe:
            # Try searching
            recipes = await recipe_service.search_recipes(recipe_name)
            if recipes:
                recipe = recipes[0]
            else:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    action="analyze_migration",
                    error=f"Recipe not found: {recipe_name}. Use list_recipes to see available recipes.",
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
                    "description": recipe.description,
                    "build_tool": build_tool,
                    "changes": changes,
                },
            )
        except FileNotFoundError as e:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="analyze_migration",
                error=str(e),
                metadata={"install_instructions": self._get_install_instructions(build_tool)},
            )

    async def _run_recipe(self, context: AgentContext, **kwargs) -> AgentResult:
        """Run an OpenRewrite recipe."""
        repo_path = Path(kwargs["repository_path"])
        recipe_name = kwargs["recipe"]
        dry_run = kwargs.get("dry_run", True)

        recipe = await recipe_service.get_recipe(recipe_name)
        if not recipe:
            recipes = await recipe_service.search_recipes(recipe_name)
            if recipes:
                recipe = recipes[0]
            else:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    action="run_recipe",
                    error=f"Recipe not found: {recipe_name}",
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
        except FileNotFoundError as e:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action="run_recipe",
                error=str(e),
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

        # LTS version mapping
        lts_upgrades = [
            (8, 11, "org.openrewrite.java.migrate.UpgradeToJava11"),
            (11, 17, "org.openrewrite.java.migrate.UpgradeToJava17"),
            (17, 21, "org.openrewrite.java.migrate.UpgradeToJava21"),
        ]

        while current < to_version:
            # Find next upgrade step
            next_step = None
            for start, end, recipe_name in lts_upgrades:
                if current <= start < to_version:
                    recipe = await recipe_service.get_recipe(recipe_name)
                    next_step = {
                        "from_version": current if current > start else start,
                        "to_version": min(end, to_version),
                        "recipe": recipe_name,
                        "recipe_display": recipe.display_name if recipe else recipe_name,
                        "description": recipe.description if recipe else "",
                    }
                    current = end
                    break

            if next_step:
                steps.append(next_step)
            else:
                break

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
                    "Execute migrations in order. Run tests after each step."
                    if len(steps) > 1
                    else "Single-step migration available."
                ) if steps else "No migration needed.",
            },
        )

    def _detect_build_tool(self, repo_path: Path) -> str | None:
        """Detect the build tool used in repository."""
        if (repo_path / "pom.xml").exists():
            return "maven"
        if (repo_path / "build.gradle").exists() or (repo_path / "build.gradle.kts").exists():
            return "gradle"
        return None

    def _get_install_instructions(self, build_tool: str) -> str:
        """Get OpenRewrite installation instructions."""
        if build_tool == "maven":
            return """Add to pom.xml:
<plugin>
    <groupId>org.openrewrite.maven</groupId>
    <artifactId>rewrite-maven-plugin</artifactId>
    <version>5.34.0</version>
</plugin>"""
        else:
            return """Add to build.gradle:
plugins {
    id("org.openrewrite.rewrite") version "6.16.0"
}"""

    async def _run_openrewrite_dry_run(
        self,
        repo_path: Path,
        recipe: Recipe,
        build_tool: str,
    ) -> list[dict]:
        """Run OpenRewrite in dry-run mode."""
        # Check if build tool is available
        if build_tool == "maven":
            cmd = ["mvn", "--version"]
            run_cmd = [
                "mvn", "-B", "rewrite:dryRun",
                f"-Drewrite.activeRecipes={recipe.name}",
            ]
        else:
            cmd = ["gradle", "--version"]
            run_cmd = [
                "./gradlew" if (repo_path / "gradlew").exists() else "gradle",
                "rewriteDryRun",
                f"-Drewrite.activeRecipe={recipe.name}",
            ]

        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=5)
        except FileNotFoundError:
            raise FileNotFoundError(f"{build_tool} not found. Install {build_tool} to use OpenRewrite.")
        except subprocess.TimeoutExpired:
            pass

        # Try to run the actual rewrite command
        changes = []
        try:
            result = subprocess.run(
                run_cmd,
                capture_output=True,
                text=True,
                cwd=repo_path,
                timeout=120,
            )

            # Parse output for changes
            for line in result.stdout.split("\n"):
                if "would be changed" in line.lower() or "change" in line.lower():
                    changes.append({"description": line.strip()})

            if not changes and result.returncode == 0:
                changes.append({"description": "Recipe ran successfully (check output for details)"})

        except subprocess.TimeoutExpired:
            changes.append({"description": "Analysis timed out - repository may be large"})
        except FileNotFoundError:
            raise FileNotFoundError(
                f"OpenRewrite plugin not configured. {self._get_install_instructions(build_tool)}"
            )

        return changes

    async def _run_openrewrite_apply(
        self,
        repo_path: Path,
        recipe: Recipe,
        build_tool: str,
    ) -> dict:
        """Run OpenRewrite and apply changes."""
        if build_tool == "maven":
            run_cmd = [
                "mvn", "-B", "rewrite:run",
                f"-Drewrite.activeRecipes={recipe.name}",
            ]
        else:
            run_cmd = [
                "./gradlew" if (repo_path / "gradlew").exists() else "gradle",
                "rewriteRun",
                f"-Drewrite.activeRecipe={recipe.name}",
            ]

        try:
            result = subprocess.run(
                run_cmd,
                capture_output=True,
                text=True,
                cwd=repo_path,
                timeout=300,
            )

            return {
                "status": "applied" if result.returncode == 0 else "failed",
                "recipe": recipe.name,
                "output": result.stdout[-2000:] if result.stdout else "",
                "errors": result.stderr[-1000:] if result.stderr else "",
            }
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "recipe": recipe.name}
        except FileNotFoundError:
            raise FileNotFoundError("OpenRewrite plugin not configured")

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
