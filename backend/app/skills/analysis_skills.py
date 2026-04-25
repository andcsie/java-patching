"""Analysis-related agent skills."""

from pathlib import Path
import uuid

from app.skills.base import (
    ParameterType,
    Skill,
    SkillCategory,
    SkillContext,
    SkillParameter,
    SkillResult,
)
from app.skills.registry import register_skill
from app.services.analyzer_service import analyzer_service
from app.services.release_notes_service import release_notes_service


@register_skill
class AnalyzeRepositorySkill(Skill):
    """Skill to analyze a repository for JDK upgrade impacts."""

    name = "analyze_repository"
    description = "Analyze a Java repository for JDK upgrade impacts. Returns a list of code locations affected by the version change."
    category = SkillCategory.ANALYSIS
    version = "1.0.0"

    @property
    def parameters(self) -> list[SkillParameter]:
        return [
            SkillParameter(
                name="repository_path",
                description="Path to the repository to analyze",
                type=ParameterType.STRING,
                required=True,
            ),
            SkillParameter(
                name="from_version",
                description="Current JDK version (e.g., '11.0.18')",
                type=ParameterType.STRING,
                required=True,
            ),
            SkillParameter(
                name="to_version",
                description="Target JDK version (e.g., '11.0.22')",
                type=ParameterType.STRING,
                required=True,
            ),
            SkillParameter(
                name="llm_provider",
                description="LLM provider to use for suggestions",
                type=ParameterType.STRING,
                required=False,
                enum=["openai", "anthropic", "gemini", "ollama"],
            ),
        ]

    async def execute(self, context: SkillContext, **kwargs) -> SkillResult:
        repo_path = Path(kwargs["repository_path"])
        from_version = kwargs["from_version"]
        to_version = kwargs["to_version"]
        llm_provider = kwargs.get("llm_provider")

        if not repo_path.exists():
            return SkillResult(success=False, error="Repository path does not exist")

        result = await analyzer_service.analyze_repository(
            repo_path=repo_path,
            from_version=from_version,
            to_version=to_version,
            llm_provider=llm_provider,
        )

        return SkillResult(
            success=result.status == "completed",
            data={
                "status": result.status,
                "risk_score": result.risk_score,
                "risk_level": result.risk_level,
                "total_files_analyzed": result.total_files_analyzed,
                "total_impacts": len(result.impacts),
                "summary": result.summary,
                "impacts": [
                    {
                        "file_path": i.location.file_path,
                        "line_number": i.location.line_number,
                        "change_type": i.change.change_type,
                        "severity": i.severity,
                        "description": i.change.description,
                        "affected_class": i.affected_class,
                        "affected_method": i.affected_method,
                    }
                    for i in result.impacts[:50]  # Limit for token constraints
                ],
            },
            error=result.error_message,
        )


@register_skill
class GetJDKChangesSkill(Skill):
    """Skill to get JDK changes between two versions."""

    name = "get_jdk_changes"
    description = "Get a list of changes (deprecations, security fixes, behavioral changes) between two JDK versions."
    category = SkillCategory.INFORMATION
    version = "1.0.0"

    @property
    def parameters(self) -> list[SkillParameter]:
        return [
            SkillParameter(
                name="from_version",
                description="Starting JDK version (e.g., '11.0.18')",
                type=ParameterType.STRING,
                required=True,
            ),
            SkillParameter(
                name="to_version",
                description="Target JDK version (e.g., '11.0.22')",
                type=ParameterType.STRING,
                required=True,
            ),
        ]

    async def execute(self, context: SkillContext, **kwargs) -> SkillResult:
        from_version = kwargs["from_version"]
        to_version = kwargs["to_version"]

        changes = await release_notes_service.get_changes_between_versions(
            from_version,
            to_version,
        )

        return SkillResult(
            success=True,
            data={
                "from_version": from_version,
                "to_version": to_version,
                "total_changes": len(changes),
                "changes": [
                    {
                        "version": c.version,
                        "change_type": c.change_type,
                        "component": c.component,
                        "description": c.description,
                        "affected_classes": c.affected_classes,
                        "cve_id": c.cve_id,
                        "migration_notes": c.migration_notes,
                    }
                    for c in changes
                ],
            },
        )


@register_skill
class GetSecurityFixesSkill(Skill):
    """Skill to get security fixes (CVEs) between JDK versions."""

    name = "get_security_fixes"
    description = "Get security vulnerabilities (CVEs) fixed between two JDK versions."
    category = SkillCategory.INFORMATION
    version = "1.0.0"

    @property
    def parameters(self) -> list[SkillParameter]:
        return [
            SkillParameter(
                name="from_version",
                description="Starting JDK version",
                type=ParameterType.STRING,
                required=True,
            ),
            SkillParameter(
                name="to_version",
                description="Target JDK version",
                type=ParameterType.STRING,
                required=True,
            ),
        ]

    async def execute(self, context: SkillContext, **kwargs) -> SkillResult:
        from_version = kwargs["from_version"]
        to_version = kwargs["to_version"]

        changes = await release_notes_service.get_changes_between_versions(
            from_version,
            to_version,
        )

        security_fixes = [c for c in changes if c.cve_id is not None]

        return SkillResult(
            success=True,
            data={
                "from_version": from_version,
                "to_version": to_version,
                "total_cves": len(security_fixes),
                "cves": [
                    {
                        "cve_id": c.cve_id,
                        "version": c.version,
                        "component": c.component,
                        "description": c.description,
                        "affected_classes": c.affected_classes,
                    }
                    for c in security_fixes
                ],
            },
        )
