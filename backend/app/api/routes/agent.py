"""Agent chat interface routes."""

import json
import uuid
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.analysis import Analysis
from app.services.llm_service import LLMService, llm_service
from app.services.repository_service import RepositoryService

router = APIRouter()


class ChatMessage(BaseModel):
    """Chat message from user."""

    content: str
    repository_id: uuid.UUID | None = None
    analysis_id: uuid.UUID | None = None
    provider: str | None = None


class ChatResponse(BaseModel):
    """Chat response."""

    content: str
    provider: str


async def get_repository_service(db: DbSession) -> RepositoryService:
    """Get repository service."""
    return RepositoryService(db)


RepoServiceDep = Annotated[RepositoryService, Depends(get_repository_service)]


@router.get("/providers")
async def get_available_providers() -> dict[str, list[str]]:
    """Get available LLM providers."""
    return {"providers": llm_service.available_providers}


@router.post("/chat", response_model=ChatResponse)
async def chat(
    message: ChatMessage,
    current_user: CurrentUser,
    db: DbSession,
    repo_service: RepoServiceDep,
) -> ChatResponse:
    """Chat with the AI agent about JDK upgrades."""
    if not llm_service.available_providers:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No LLM providers configured",
        )

    # Build context from repository/analysis if provided
    context = await _build_context(
        db,
        repo_service,
        current_user.id,
        message.repository_id,
        message.analysis_id,
    )

    messages = [
        {
            "role": "system",
            "content": """You are an expert Java developer assistant specializing in JDK upgrades and migrations.
You help developers understand the impact of JDK version changes on their codebase.
You can:
- Explain JDK changes and their implications
- Suggest code fixes for deprecated or removed APIs
- Provide migration strategies and best practices
- Answer questions about Java compatibility

Be concise, accurate, and provide code examples when helpful."""
            + (f"\n\nContext about the current repository/analysis:\n{context}" if context else ""),
        },
        {
            "role": "user",
            "content": message.content,
        },
    ]

    try:
        provider = message.provider or llm_service.available_providers[0]
        response = await llm_service.complete(messages, provider)
        return ChatResponse(content=response, provider=provider)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM error: {str(e)}",
        )


@router.post("/chat/stream")
async def chat_stream(
    message: ChatMessage,
    current_user: CurrentUser,
    db: DbSession,
    repo_service: RepoServiceDep,
) -> StreamingResponse:
    """Stream chat response from the AI agent."""
    if not llm_service.available_providers:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No LLM providers configured",
        )

    context = await _build_context(
        db,
        repo_service,
        current_user.id,
        message.repository_id,
        message.analysis_id,
    )

    messages = [
        {
            "role": "system",
            "content": """You are an expert Java developer assistant specializing in JDK upgrades and migrations.
You help developers understand the impact of JDK version changes on their codebase.
Be concise, accurate, and provide code examples when helpful."""
            + (f"\n\nContext:\n{context}" if context else ""),
        },
        {
            "role": "user",
            "content": message.content,
        },
    ]

    provider = message.provider or llm_service.available_providers[0]

    async def generate() -> AsyncIterator[bytes]:
        try:
            async for chunk in llm_service.stream(messages, provider):
                yield f"data: {json.dumps({'content': chunk})}\n\n".encode()
            yield b"data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n".encode()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/suggest-fix")
async def suggest_fix(
    code: str,
    issue_description: str,
    current_user: CurrentUser,
    provider: str | None = None,
) -> dict[str, str]:
    """Get a suggested fix for a specific code issue."""
    if not llm_service.available_providers:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No LLM providers configured",
        )

    messages = [
        {
            "role": "system",
            "content": """You are an expert Java developer. Provide a concise fix for the given code issue.
Return only the fixed code with minimal explanation.""",
        },
        {
            "role": "user",
            "content": f"""Original code:
```java
{code}
```

Issue: {issue_description}

Provide the fixed code.""",
        },
    ]

    try:
        provider = provider or llm_service.available_providers[0]
        response = await llm_service.complete(messages, provider)
        return {"fix": response, "provider": provider}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM error: {str(e)}",
        )


@router.post("/explain-change")
async def explain_change(
    change_description: str,
    current_user: CurrentUser,
    provider: str | None = None,
) -> dict[str, str]:
    """Get a detailed explanation of a JDK change."""
    if not llm_service.available_providers:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No LLM providers configured",
        )

    messages = [
        {
            "role": "system",
            "content": """You are an expert on JDK internals and Java evolution.
Explain the given JDK change in detail, including:
- Why the change was made
- What code patterns are affected
- How to migrate affected code
- Any gotchas or edge cases""",
        },
        {
            "role": "user",
            "content": f"Explain this JDK change:\n{change_description}",
        },
    ]

    try:
        provider = provider or llm_service.available_providers[0]
        response = await llm_service.complete(messages, provider)
        return {"explanation": response, "provider": provider}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM error: {str(e)}",
        )


async def _build_context(
    db: DbSession,
    repo_service: RepositoryService,
    user_id: uuid.UUID,
    repository_id: uuid.UUID | None,
    analysis_id: uuid.UUID | None,
) -> str:
    """Build context string from repository and analysis."""
    context_parts = []

    if repository_id:
        repo = await repo_service.get_by_id(repository_id)
        if repo and repo.owner_id == user_id:
            context_parts.append(
                f"Repository: {repo.name}\n"
                f"Current JDK: {repo.current_jdk_version or 'Unknown'}\n"
                f"Target JDK: {repo.target_jdk_version or 'Unknown'}"
            )

    if analysis_id:
        result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
        analysis = result.scalar_one_or_none()
        if analysis and analysis.user_id == user_id:
            impacts = analysis.impacts or []
            context_parts.append(
                f"\nAnalysis: {analysis.from_version} → {analysis.to_version}\n"
                f"Risk Score: {analysis.risk_score}/100\n"
                f"Total Impacts: {len(impacts)}\n"
                f"Summary: {analysis.summary or 'No summary available'}"
            )

            # Add top impacts
            if impacts:
                context_parts.append("\nTop impacts:")
                for impact in impacts[:5]:
                    context_parts.append(
                        f"- {impact.file_path}:{impact.line_number}: "
                        f"{impact.description[:100]}..."
                    )

    return "\n".join(context_parts)
