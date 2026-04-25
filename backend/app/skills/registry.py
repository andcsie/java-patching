"""Skill registry for managing and discovering skills."""

from typing import Type

from app.skills.base import Skill, SkillCategory, SkillContext, SkillResult


class SkillRegistry:
    """Registry for managing agent skills."""

    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self._categories: dict[SkillCategory, list[str]] = {
            category: [] for category in SkillCategory
        }

    def register(self, skill_class: Type[Skill]) -> None:
        """Register a skill class."""
        skill = skill_class()
        self._skills[skill.name] = skill
        self._categories[skill.category].append(skill.name)

    def unregister(self, name: str) -> bool:
        """Unregister a skill by name."""
        if name in self._skills:
            skill = self._skills[name]
            self._categories[skill.category].remove(name)
            del self._skills[name]
            return True
        return False

    def get(self, name: str) -> Skill | None:
        """Get a skill by name."""
        return self._skills.get(name)

    def list_skills(self, category: SkillCategory | None = None) -> list[Skill]:
        """List all registered skills, optionally filtered by category."""
        if category:
            return [self._skills[name] for name in self._categories[category]]
        return list(self._skills.values())

    def list_skill_names(self, category: SkillCategory | None = None) -> list[str]:
        """List all skill names."""
        if category:
            return self._categories[category].copy()
        return list(self._skills.keys())

    def get_tool_definitions(self, category: SkillCategory | None = None) -> list[dict]:
        """Get tool definitions for all skills (for LLM function calling)."""
        skills = self.list_skills(category)
        return [skill.get_tool_definition() for skill in skills]

    async def execute(
        self,
        skill_name: str,
        context: SkillContext,
        **kwargs,
    ) -> SkillResult:
        """Execute a skill by name."""
        skill = self.get(skill_name)
        if not skill:
            return SkillResult(
                success=False,
                error=f"Skill not found: {skill_name}",
            )

        # Validate parameters
        valid, error = skill.validate_parameters(**kwargs)
        if not valid:
            return SkillResult(success=False, error=error)

        try:
            return await skill.execute(context, **kwargs)
        except Exception as e:
            return SkillResult(
                success=False,
                error=f"Skill execution failed: {str(e)}",
            )

    def get_skill_info(self, name: str) -> dict | None:
        """Get information about a skill."""
        skill = self.get(name)
        if not skill:
            return None

        return {
            "name": skill.name,
            "description": skill.description,
            "category": skill.category,
            "version": skill.version,
            "parameters": [
                {
                    "name": p.name,
                    "description": p.description,
                    "type": p.type,
                    "required": p.required,
                    "default": p.default,
                }
                for p in skill.parameters
            ],
        }


# Global registry instance
skill_registry = SkillRegistry()


def register_skill(skill_class: Type[Skill]) -> Type[Skill]:
    """Decorator to register a skill class."""
    skill_registry.register(skill_class)
    return skill_class
