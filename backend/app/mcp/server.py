"""FastMCP Server for Java Patching tools.

This module exposes all agent capabilities as MCP tools using the FastMCP library.
"""

import uuid
from pathlib import Path

from fastmcp import FastMCP

from app.agents import AgentContext, agent_registry

# Import agents to ensure they're registered
from app.agents import openrewrite_agent, renovate_agent  # noqa: F401

# Create FastMCP server
mcp = FastMCP(
    name="java-patching",
    version="1.0.0",
    description="JDK version management, migration, and code transformation tools",
)


# =============================================================================
# Renovate Agent Tools
# =============================================================================


@mcp.tool()
async def detect_jdk_version(repository_path: str) -> dict:
    """Detect the current JDK version from build files in a repository.

    Scans pom.xml, build.gradle, .java-version, .sdkmanrc, and .tool-versions
    to determine the JDK version used by the project.

    Args:
        repository_path: Path to the repository to analyze

    Returns:
        JDK version information including major, minor, patch, and source file
    """
    context = _create_context()
    result = await agent_registry.execute(
        "renovate",
        "detect_version",
        context,
        repository_path=repository_path,
    )
    return result.to_dict()


@mcp.tool()
async def get_available_patches(repository_path: str, include_ea: bool = False) -> dict:
    """Get available JDK patch versions for the current major version.

    Queries the Adoptium API for newer patch releases.

    Args:
        repository_path: Path to the repository
        include_ea: Include early access releases

    Returns:
        List of available patches with version, release date, and security fixes
    """
    context = _create_context()
    result = await agent_registry.execute(
        "renovate",
        "get_available_patches",
        context,
        repository_path=repository_path,
        include_ea=include_ea,
    )
    return result.to_dict()


@mcp.tool()
async def preview_version_bump(repository_path: str, target_version: str) -> dict:
    """Preview changes needed to bump JDK version.

    Shows what files would be modified and the diffs for each change.

    Args:
        repository_path: Path to the repository
        target_version: Target JDK version (e.g., '11.0.22')

    Returns:
        List of file changes with diffs
    """
    context = _create_context()
    result = await agent_registry.execute(
        "renovate",
        "preview_version_bump",
        context,
        repository_path=repository_path,
        target_version=target_version,
    )
    return result.to_dict()


@mcp.tool()
async def apply_version_bump(repository_path: str, target_version: str) -> dict:
    """Apply a version bump to update JDK version in build files.

    Modifies pom.xml, build.gradle, and other version files.

    Args:
        repository_path: Path to the repository
        target_version: Target JDK version to apply

    Returns:
        List of files that were modified
    """
    context = _create_context()
    result = await agent_registry.execute(
        "renovate",
        "apply_version_bump",
        context,
        repository_path=repository_path,
        target_version=target_version,
    )
    return result.to_dict()


@mcp.tool()
async def generate_renovate_config(
    repository_path: str,
    target_jdk: str | None = None,
    save: bool = False,
) -> dict:
    """Generate a renovate.json configuration file.

    Creates a Renovate configuration optimized for JDK patch updates.

    Args:
        repository_path: Path to the repository
        target_jdk: Optional maximum JDK version constraint
        save: Save the config to renovate.json

    Returns:
        Generated configuration and optionally the save path
    """
    context = _create_context()
    result = await agent_registry.execute(
        "renovate",
        "generate_config",
        context,
        repository_path=repository_path,
        target_jdk=target_jdk,
        save=save,
    )
    return result.to_dict()


# =============================================================================
# OpenRewrite Agent Tools
# =============================================================================


@mcp.tool()
async def list_migration_recipes(category: str = "all") -> dict:
    """List available OpenRewrite recipes for Java migration.

    Args:
        category: Filter by category - 'migration', 'security', 'testing', or 'all'

    Returns:
        List of available recipes with descriptions and estimated effort
    """
    context = _create_context()
    result = await agent_registry.execute(
        "openrewrite",
        "list_recipes",
        context,
        category=category,
    )
    return result.to_dict()


@mcp.tool()
async def analyze_migration(repository_path: str, recipe: str) -> dict:
    """Analyze what changes a migration recipe would make.

    Performs a dry-run analysis without applying changes.

    Args:
        repository_path: Path to the repository
        recipe: Recipe name or shorthand (e.g., 'java11to17', 'jakarta_ee9')

    Returns:
        Analysis of changes that would be made
    """
    context = _create_context()
    result = await agent_registry.execute(
        "openrewrite",
        "analyze_migration",
        context,
        repository_path=repository_path,
        recipe=recipe,
    )
    return result.to_dict()


@mcp.tool()
async def run_migration_recipe(
    repository_path: str,
    recipe: str,
    dry_run: bool = True,
) -> dict:
    """Run an OpenRewrite recipe to transform code.

    Args:
        repository_path: Path to the repository
        recipe: Recipe name or shorthand
        dry_run: Preview changes without applying (default: True)

    Returns:
        Changes made or previewed
    """
    context = _create_context()
    result = await agent_registry.execute(
        "openrewrite",
        "run_recipe",
        context,
        repository_path=repository_path,
        recipe=recipe,
        dry_run=dry_run,
    )
    return result.to_dict()


@mcp.tool()
async def suggest_migration_path(from_version: int, to_version: int) -> dict:
    """Suggest the best migration path between JDK versions.

    Provides step-by-step migration recommendations for major version upgrades.

    Args:
        from_version: Current JDK major version (e.g., 8, 11, 17)
        to_version: Target JDK major version (e.g., 17, 21)

    Returns:
        Ordered list of migration steps with recipes and estimated effort
    """
    context = _create_context()
    result = await agent_registry.execute(
        "openrewrite",
        "suggest_migration_path",
        context,
        from_version=from_version,
        to_version=to_version,
    )
    return result.to_dict()


@mcp.tool()
async def scan_security_vulnerabilities(repository_path: str) -> dict:
    """Scan repository for security vulnerabilities.

    Uses OpenRewrite's OWASP Top 10 recipes to identify security issues.

    Args:
        repository_path: Path to the repository

    Returns:
        List of security issues found and available fixes
    """
    context = _create_context()
    result = await agent_registry.execute(
        "openrewrite",
        "scan_security",
        context,
        repository_path=repository_path,
    )
    return result.to_dict()


# =============================================================================
# Agent Management Tools
# =============================================================================


@mcp.tool()
async def list_agents() -> dict:
    """List all available agents and their capabilities.

    Returns:
        List of agents with their capabilities and actions
    """
    agents = []
    for agent in agent_registry.list_agents():
        agents.append({
            "name": agent.name,
            "description": agent.description,
            "version": agent.version,
            "capabilities": [cap.value for cap in agent.capabilities],
            "actions": [
                {
                    "name": action.name,
                    "description": action.description,
                }
                for action in agent.actions
            ],
        })
    return {"agents": agents}


@mcp.tool()
async def check_agent_health() -> dict:
    """Check health status of all agents.

    Verifies each agent can execute (e.g., external tools are available).

    Returns:
        Health status for each agent
    """
    health = await agent_registry.health_check_all()
    return {"health": health}


# =============================================================================
# Resources
# =============================================================================


@mcp.resource("jdk://versions/lts")
async def get_lts_versions() -> str:
    """Get information about JDK LTS versions."""
    import json

    return json.dumps({
        "lts_versions": {
            "8": {"latest": "8u412", "support_until": "2030-12"},
            "11": {"latest": "11.0.23", "support_until": "2026-09"},
            "17": {"latest": "17.0.11", "support_until": "2029-09"},
            "21": {"latest": "21.0.3", "support_until": "2031-09"},
        },
        "note": "Use detect_jdk_version and get_available_patches for real-time data",
    })


@mcp.resource("agents://list")
async def get_agents_resource() -> str:
    """Get list of available agents."""
    import json

    agents = []
    for agent in agent_registry.list_agents():
        agents.append({
            "name": agent.name,
            "description": agent.description,
            "capabilities": [cap.value for cap in agent.capabilities],
        })
    return json.dumps({"agents": agents})


# =============================================================================
# Prompts
# =============================================================================


@mcp.prompt()
def analyze_upgrade(repository_path: str, target_version: str) -> str:
    """Prompt to analyze a JDK upgrade for a repository."""
    return f"""Analyze the JDK upgrade impact for the repository at {repository_path}.

1. First, use detect_jdk_version to find the current version
2. Use get_available_patches to see available patch updates
3. If upgrading to {target_version}, use suggest_migration_path to plan the upgrade
4. For patch upgrades, use preview_version_bump
5. For major upgrades, use analyze_migration with appropriate recipes
6. Summarize findings and recommend next steps"""


@mcp.prompt()
def migration_plan(from_version: int, to_version: int) -> str:
    """Prompt to create a migration plan between JDK versions."""
    return f"""Create a comprehensive migration plan from JDK {from_version} to {to_version}.

1. Use suggest_migration_path to get the recommended migration steps
2. Use list_migration_recipes to see available transformation recipes
3. For each step:
   - Identify breaking changes
   - List deprecated APIs to migrate
   - Note security fixes included
4. Provide testing recommendations for each migration step
5. Estimate total effort and risk level"""


@mcp.prompt()
def security_audit(repository_path: str) -> str:
    """Prompt to perform a security audit on a repository."""
    return f"""Perform a security audit on the repository at {repository_path}.

1. Use detect_jdk_version to check the current JDK version
2. Use get_available_patches to identify security patches available
3. Use scan_security_vulnerabilities to find code-level issues
4. Summarize:
   - Missing security patches
   - Code vulnerabilities found
   - Recommended immediate actions
   - Long-term security improvements"""


# =============================================================================
# Helpers
# =============================================================================


def _create_context() -> AgentContext:
    """Create a default agent context for MCP calls."""
    return AgentContext(
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        metadata={"source": "mcp"},
    )
