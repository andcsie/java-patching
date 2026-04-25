"""API routes for the agent skill system."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.skills import SkillCategory, SkillContext, skill_registry

# Import skills to register them
from app.skills import analysis_skills, llm_skills, version_skills  # noqa: F401

router = APIRouter()


class SkillExecutionRequest(BaseModel):
    """Request to execute a skill."""

    skill_name: str
    parameters: dict[str, Any]
    repository_id: str | None = None
    analysis_id: str | None = None


class SkillExecutionResponse(BaseModel):
    """Response from skill execution."""

    success: bool
    data: Any | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None


class SkillInfo(BaseModel):
    """Information about a skill."""

    name: str
    description: str
    category: str
    version: str
    parameters: list[dict[str, Any]]


@router.get("/", response_model=list[SkillInfo])
async def list_skills(
    current_user: CurrentUser,
    category: str | None = None,
):
    """List all available skills."""
    cat = SkillCategory(category) if category else None
    skills = skill_registry.list_skills(cat)

    return [
        SkillInfo(
            name=skill.name,
            description=skill.description,
            category=skill.category,
            version=skill.version,
            parameters=[
                {
                    "name": p.name,
                    "description": p.description,
                    "type": p.type,
                    "required": p.required,
                    "default": p.default,
                    "enum": p.enum,
                }
                for p in skill.parameters
            ],
        )
        for skill in skills
    ]


@router.get("/categories")
async def list_categories(current_user: CurrentUser):
    """List all skill categories."""
    return {
        "categories": [
            {"name": cat.value, "count": len(skill_registry.list_skill_names(cat))}
            for cat in SkillCategory
        ]
    }


@router.get("/tools")
async def get_tool_definitions(
    current_user: CurrentUser,
    category: str | None = None,
):
    """Get tool definitions for LLM function calling."""
    cat = SkillCategory(category) if category else None
    return {"tools": skill_registry.get_tool_definitions(cat)}


@router.get("/{skill_name}", response_model=SkillInfo | None)
async def get_skill(skill_name: str, current_user: CurrentUser):
    """Get information about a specific skill."""
    info = skill_registry.get_skill_info(skill_name)
    if not info:
        raise HTTPException(status_code=404, detail="Skill not found")

    return SkillInfo(**info)


@router.post("/execute", response_model=SkillExecutionResponse)
async def execute_skill(
    request: SkillExecutionRequest,
    current_user: CurrentUser,
):
    """Execute a skill with the given parameters."""
    import uuid

    context = SkillContext(
        user_id=current_user.id,
        repository_id=uuid.UUID(request.repository_id) if request.repository_id else None,
        analysis_id=uuid.UUID(request.analysis_id) if request.analysis_id else None,
    )

    result = await skill_registry.execute(
        request.skill_name,
        context,
        **request.parameters,
    )

    return SkillExecutionResponse(
        success=result.success,
        data=result.data,
        error=result.error,
        metadata=result.metadata,
    )
