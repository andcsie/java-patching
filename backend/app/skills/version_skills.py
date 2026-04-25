"""Version management agent skills."""

from pathlib import Path

from app.skills.base import (
    ParameterType,
    Skill,
    SkillCategory,
    SkillContext,
    SkillParameter,
    SkillResult,
)
from app.skills.registry import register_skill
from app.services.renovate_service import renovate_service


@register_skill
class DetectJDKVersionSkill(Skill):
    """Skill to detect JDK version from a repository."""

    name = "detect_jdk_version"
    description = "Detect the current JDK version configured in a Java repository by scanning build files (pom.xml, build.gradle, .java-version, etc.)."
    category = SkillCategory.VERSION_MANAGEMENT
    version = "1.0.0"

    @property
    def parameters(self) -> list[SkillParameter]:
        return [
            SkillParameter(
                name="repository_path",
                description="Path to the repository",
                type=ParameterType.STRING,
                required=True,
            ),
        ]

    async def execute(self, context: SkillContext, **kwargs) -> SkillResult:
        repo_path = Path(kwargs["repository_path"])

        if not repo_path.exists():
            return SkillResult(success=False, error="Repository path does not exist")

        version = await renovate_service.detect_jdk_version(repo_path)

        if not version:
            return SkillResult(
                success=False,
                error="Could not detect JDK version from build files",
            )

        return SkillResult(
            success=True,
            data={
                "major": version.major,
                "minor": version.minor,
                "patch": version.patch,
                "full_version": version.full,
                "source_file": version.source_file,
                "source_line": version.source_line,
            },
        )


@register_skill
class GetAvailablePatchesSkill(Skill):
    """Skill to get available JDK patches."""

    name = "get_available_patches"
    description = "Get available JDK patch versions for a repository's current JDK version."
    category = SkillCategory.VERSION_MANAGEMENT
    version = "1.0.0"

    @property
    def parameters(self) -> list[SkillParameter]:
        return [
            SkillParameter(
                name="repository_path",
                description="Path to the repository",
                type=ParameterType.STRING,
                required=True,
            ),
        ]

    async def execute(self, context: SkillContext, **kwargs) -> SkillResult:
        repo_path = Path(kwargs["repository_path"])

        if not repo_path.exists():
            return SkillResult(success=False, error="Repository path does not exist")

        current = await renovate_service.detect_jdk_version(repo_path)
        if not current:
            return SkillResult(
                success=False,
                error="Could not detect JDK version",
            )

        patches = await renovate_service.get_available_patches(current)

        return SkillResult(
            success=True,
            data={
                "current_version": current.full,
                "available_patches": [
                    {
                        "version": p.version,
                        "release_date": p.release_date,
                        "is_lts": p.is_lts,
                        "security_fixes": p.security_fixes,
                        "release_notes_url": p.release_notes_url,
                    }
                    for p in patches
                ],
            },
        )


@register_skill
class PreviewVersionBumpSkill(Skill):
    """Skill to preview version bump changes."""

    name = "preview_version_bump"
    description = "Preview the file changes needed to bump JDK version without applying them."
    category = SkillCategory.VERSION_MANAGEMENT
    version = "1.0.0"

    @property
    def parameters(self) -> list[SkillParameter]:
        return [
            SkillParameter(
                name="repository_path",
                description="Path to the repository",
                type=ParameterType.STRING,
                required=True,
            ),
            SkillParameter(
                name="target_version",
                description="Target JDK version (e.g., '11.0.22')",
                type=ParameterType.STRING,
                required=True,
            ),
        ]

    async def execute(self, context: SkillContext, **kwargs) -> SkillResult:
        repo_path = Path(kwargs["repository_path"])
        target_version = kwargs["target_version"]

        if not repo_path.exists():
            return SkillResult(success=False, error="Repository path does not exist")

        bumps = await renovate_service.generate_version_bump(repo_path, target_version)

        if not bumps:
            return SkillResult(
                success=True,
                data={
                    "message": "No version bumps needed or target version invalid",
                    "bumps": [],
                },
            )

        return SkillResult(
            success=True,
            data={
                "target_version": target_version,
                "bumps": [
                    {
                        "file_path": b.file_path,
                        "old_version": b.old_version,
                        "new_version": b.new_version,
                        "line_number": b.line_number,
                        "diff": b.diff,
                    }
                    for b in bumps
                ],
            },
        )


@register_skill
class ApplyVersionBumpSkill(Skill):
    """Skill to apply version bump changes."""

    name = "apply_version_bump"
    description = "Apply JDK version bump to repository build files."
    category = SkillCategory.VERSION_MANAGEMENT
    version = "1.0.0"

    @property
    def parameters(self) -> list[SkillParameter]:
        return [
            SkillParameter(
                name="repository_path",
                description="Path to the repository",
                type=ParameterType.STRING,
                required=True,
            ),
            SkillParameter(
                name="target_version",
                description="Target JDK version (e.g., '11.0.22')",
                type=ParameterType.STRING,
                required=True,
            ),
        ]

    async def execute(self, context: SkillContext, **kwargs) -> SkillResult:
        repo_path = Path(kwargs["repository_path"])
        target_version = kwargs["target_version"]

        if not repo_path.exists():
            return SkillResult(success=False, error="Repository path does not exist")

        bumps = await renovate_service.generate_version_bump(repo_path, target_version)

        applied = []
        failed = []

        for bump in bumps:
            success = await renovate_service.apply_version_bump(bump)
            if success:
                applied.append(bump.file_path)
            else:
                failed.append(bump.file_path)

        return SkillResult(
            success=len(failed) == 0,
            data={
                "target_version": target_version,
                "applied_files": applied,
                "failed_files": failed,
            },
            error=f"Failed to update: {failed}" if failed else None,
        )


@register_skill
class GenerateRenovateConfigSkill(Skill):
    """Skill to generate Renovate configuration."""

    name = "generate_renovate_config"
    description = "Generate a renovate.json configuration file for automated dependency updates."
    category = SkillCategory.VERSION_MANAGEMENT
    version = "1.0.0"

    @property
    def parameters(self) -> list[SkillParameter]:
        return [
            SkillParameter(
                name="repository_path",
                description="Path to the repository",
                type=ParameterType.STRING,
                required=True,
            ),
            SkillParameter(
                name="target_jdk",
                description="Maximum JDK version to allow (optional)",
                type=ParameterType.STRING,
                required=False,
            ),
            SkillParameter(
                name="save_to_file",
                description="Whether to save the config to renovate.json",
                type=ParameterType.BOOLEAN,
                required=False,
                default=False,
            ),
        ]

    async def execute(self, context: SkillContext, **kwargs) -> SkillResult:
        repo_path = Path(kwargs["repository_path"])
        target_jdk = kwargs.get("target_jdk")
        save_to_file = kwargs.get("save_to_file", False)

        if not repo_path.exists():
            return SkillResult(success=False, error="Repository path does not exist")

        config = await renovate_service.generate_renovate_config(repo_path, target_jdk)

        result_data = {"config": config}

        if save_to_file:
            config_path = await renovate_service.save_renovate_config(repo_path, config)
            result_data["saved_to"] = config_path

        return SkillResult(success=True, data=result_data)
