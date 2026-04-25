"""Audit and history routes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.audit import (
    AnalysisHistoryQuery,
    AnalysisHistoryResponse,
    AuditLogQuery,
    AuditLogResponse,
)
from app.services.audit_service import AuditService

router = APIRouter()


async def get_audit_service(db: DbSession) -> AuditService:
    """Get audit service."""
    return AuditService(db)


AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]


@router.get("/logs", response_model=list[AuditLogResponse])
async def get_audit_logs(
    current_user: CurrentUser,
    audit_service: AuditServiceDep,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    action: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLogResponse]:
    """Get audit logs for the current user."""
    query = AuditLogQuery(
        user_id=current_user.id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        limit=limit,
        offset=offset,
    )

    logs = await audit_service.get_audit_trail(query)
    return [AuditLogResponse.model_validate(log) for log in logs]


@router.get("/activity", response_model=list[AuditLogResponse])
async def get_user_activity(
    current_user: CurrentUser,
    audit_service: AuditServiceDep,
    limit: int = 50,
) -> list[AuditLogResponse]:
    """Get recent activity for the current user."""
    logs = await audit_service.get_user_activity(current_user.id, limit)
    return [AuditLogResponse.model_validate(log) for log in logs]


@router.get("/history", response_model=list[AnalysisHistoryResponse])
async def get_analysis_history(
    current_user: CurrentUser,
    audit_service: AuditServiceDep,
    repository_id: uuid.UUID | None = None,
    from_version: str | None = None,
    to_version: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AnalysisHistoryResponse]:
    """Get historical analyses for the current user."""
    query = AnalysisHistoryQuery(
        user_id=current_user.id,
        repository_id=repository_id,
        from_version=from_version,
        to_version=to_version,
        limit=limit,
        offset=offset,
    )

    history = await audit_service.get_analysis_history(query)
    return [AnalysisHistoryResponse.model_validate(h) for h in history]


@router.get("/history/{history_id}", response_model=AnalysisHistoryResponse)
async def get_analysis_history_detail(
    history_id: uuid.UUID,
    current_user: CurrentUser,
    audit_service: AuditServiceDep,
) -> AnalysisHistoryResponse:
    """Get a specific historical analysis."""
    history = await audit_service.get_analysis_history_by_id(history_id)

    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History entry not found",
        )

    if history.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this history entry",
        )

    return AnalysisHistoryResponse.model_validate(history)


@router.get("/repository/{repository_id}/history", response_model=list[AnalysisHistoryResponse])
async def get_repository_history(
    repository_id: uuid.UUID,
    current_user: CurrentUser,
    audit_service: AuditServiceDep,
    limit: int = 10,
) -> list[AnalysisHistoryResponse]:
    """Get analysis history for a specific repository."""
    # First check we have access (will be filtered by user in the query)
    query = AnalysisHistoryQuery(
        user_id=current_user.id,
        repository_id=repository_id,
        limit=limit,
    )

    history = await audit_service.get_analysis_history(query)
    return [AnalysisHistoryResponse.model_validate(h) for h in history]
