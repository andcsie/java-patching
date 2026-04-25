"""LLM-powered agent skills for code assistance."""

from app.skills.base import (
    ParameterType,
    Skill,
    SkillCategory,
    SkillContext,
    SkillParameter,
    SkillResult,
)
from app.skills.registry import register_skill
from app.services.llm_service import llm_service


@register_skill
class ExplainJDKChangeSkill(Skill):
    """Skill to explain a JDK change in detail."""

    name = "explain_jdk_change"
    description = "Get a detailed explanation of a JDK change, including why it was made, what code is affected, and how to migrate."
    category = SkillCategory.INFORMATION
    version = "1.0.0"

    @property
    def parameters(self) -> list[SkillParameter]:
        return [
            SkillParameter(
                name="change_description",
                description="Description of the JDK change to explain",
                type=ParameterType.STRING,
                required=True,
            ),
            SkillParameter(
                name="llm_provider",
                description="LLM provider to use",
                type=ParameterType.STRING,
                required=False,
                enum=["openai", "anthropic", "gemini", "ollama"],
            ),
        ]

    async def execute(self, context: SkillContext, **kwargs) -> SkillResult:
        change_description = kwargs["change_description"]
        provider = kwargs.get("llm_provider")

        if not llm_service.available_providers:
            return SkillResult(
                success=False,
                error="No LLM providers configured",
            )

        messages = [
            {
                "role": "system",
                "content": """You are an expert on JDK internals and Java evolution.
Explain the given JDK change in detail, including:
1. Why the change was made
2. What code patterns are affected
3. How to migrate affected code
4. Any gotchas or edge cases

Be concise but thorough.""",
            },
            {
                "role": "user",
                "content": f"Explain this JDK change:\n{change_description}",
            },
        ]

        try:
            response = await llm_service.complete(messages, provider)
            return SkillResult(
                success=True,
                data={
                    "explanation": response,
                    "provider": provider or llm_service.available_providers[0],
                },
            )
        except Exception as e:
            return SkillResult(success=False, error=str(e))


@register_skill
class SuggestCodeFixSkill(Skill):
    """Skill to suggest a fix for code affected by JDK changes."""

    name = "suggest_code_fix"
    description = "Get a suggested code fix for code affected by a JDK change or deprecation."
    category = SkillCategory.CODE_TRANSFORMATION
    version = "1.0.0"

    @property
    def parameters(self) -> list[SkillParameter]:
        return [
            SkillParameter(
                name="code_snippet",
                description="The code that needs to be fixed",
                type=ParameterType.STRING,
                required=True,
            ),
            SkillParameter(
                name="issue_description",
                description="Description of the issue (e.g., deprecated API, removed method)",
                type=ParameterType.STRING,
                required=True,
            ),
            SkillParameter(
                name="llm_provider",
                description="LLM provider to use",
                type=ParameterType.STRING,
                required=False,
                enum=["openai", "anthropic", "gemini", "ollama"],
            ),
        ]

    async def execute(self, context: SkillContext, **kwargs) -> SkillResult:
        code_snippet = kwargs["code_snippet"]
        issue_description = kwargs["issue_description"]
        provider = kwargs.get("llm_provider")

        if not llm_service.available_providers:
            return SkillResult(
                success=False,
                error="No LLM providers configured",
            )

        response = await llm_service.analyze_code_impact(
            code_snippet,
            issue_description,
            provider,
        )

        return SkillResult(
            success=True,
            data={
                "suggested_fix": response,
                "provider": provider or llm_service.available_providers[0],
            },
        )


@register_skill
class GenerateMigrationPlanSkill(Skill):
    """Skill to generate a migration plan for JDK upgrade."""

    name = "generate_migration_plan"
    description = "Generate a comprehensive migration plan for upgrading between JDK versions, based on identified impacts."
    category = SkillCategory.ANALYSIS
    version = "1.0.0"

    @property
    def parameters(self) -> list[SkillParameter]:
        return [
            SkillParameter(
                name="impacts",
                description="List of impacts (objects with file_path, description, change_type, severity)",
                type=ParameterType.ARRAY,
                required=True,
            ),
            SkillParameter(
                name="from_version",
                description="Current JDK version",
                type=ParameterType.STRING,
                required=True,
            ),
            SkillParameter(
                name="to_version",
                description="Target JDK version",
                type=ParameterType.STRING,
                required=True,
            ),
            SkillParameter(
                name="llm_provider",
                description="LLM provider to use",
                type=ParameterType.STRING,
                required=False,
                enum=["openai", "anthropic", "gemini", "ollama"],
            ),
        ]

    async def execute(self, context: SkillContext, **kwargs) -> SkillResult:
        impacts = kwargs["impacts"]
        from_version = kwargs["from_version"]
        to_version = kwargs["to_version"]
        provider = kwargs.get("llm_provider")

        if not llm_service.available_providers:
            return SkillResult(
                success=False,
                error="No LLM providers configured",
            )

        migration_plan = await llm_service.generate_migration_plan(
            impacts,
            from_version,
            to_version,
            provider,
        )

        return SkillResult(
            success=True,
            data={
                "migration_plan": migration_plan,
                "from_version": from_version,
                "to_version": to_version,
                "provider": provider or llm_service.available_providers[0],
            },
        )
