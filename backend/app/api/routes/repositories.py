"""Repository management routes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.repository import (
    RepositoryCloneResponse,
    RepositoryCreate,
    RepositoryResponse,
    RepositoryUpdate,
)
from app.services.audit_service import AuditService
from app.services.repository_service import RepositoryService

router = APIRouter()


async def get_repository_service(db: DbSession) -> RepositoryService:
    """Get repository service."""
    return RepositoryService(db)


async def get_audit_service(db: DbSession) -> AuditService:
    """Get audit service."""
    return AuditService(db)


RepoServiceDep = Annotated[RepositoryService, Depends(get_repository_service)]
AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]


@router.post("/", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def create_repository(
    repo_data: RepositoryCreate,
    current_user: CurrentUser,
    repo_service: RepoServiceDep,
    audit_service: AuditServiceDep,
    request: Request,
) -> RepositoryResponse:
    """Create a new repository."""
    repo = await repo_service.create(current_user.id, repo_data)

    await audit_service.log_action(
        action="repository_created",
        entity_type="repository",
        entity_id=repo.id,
        user_id=current_user.id,
        details={"name": repo.name, "url": repo.url},
        request=request,
    )

    return RepositoryResponse.model_validate(repo)


@router.get("/", response_model=list[RepositoryResponse])
async def list_repositories(
    current_user: CurrentUser,
    repo_service: RepoServiceDep,
) -> list[RepositoryResponse]:
    """List all repositories for the current user."""
    repos = await repo_service.get_by_user(current_user.id)
    return [RepositoryResponse.model_validate(r) for r in repos]


@router.get("/{repository_id}", response_model=RepositoryResponse)
async def get_repository(
    repository_id: uuid.UUID,
    current_user: CurrentUser,
    repo_service: RepoServiceDep,
) -> RepositoryResponse:
    """Get a specific repository."""
    repo = await repo_service.get_by_id(repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    if repo.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this repository",
        )

    return RepositoryResponse.model_validate(repo)


@router.patch("/{repository_id}", response_model=RepositoryResponse)
async def update_repository(
    repository_id: uuid.UUID,
    repo_data: RepositoryUpdate,
    current_user: CurrentUser,
    repo_service: RepoServiceDep,
    audit_service: AuditServiceDep,
    request: Request,
) -> RepositoryResponse:
    """Update a repository."""
    repo = await repo_service.get_by_id(repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    if repo.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this repository",
        )

    updated_repo = await repo_service.update(repo, repo_data)

    await audit_service.log_action(
        action="repository_updated",
        entity_type="repository",
        entity_id=repo.id,
        user_id=current_user.id,
        details=repo_data.model_dump(exclude_unset=True),
        request=request,
    )

    return RepositoryResponse.model_validate(updated_repo)


@router.delete("/{repository_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repository(
    repository_id: uuid.UUID,
    current_user: CurrentUser,
    repo_service: RepoServiceDep,
    audit_service: AuditServiceDep,
    request: Request,
) -> None:
    """Delete a repository."""
    repo = await repo_service.get_by_id(repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    if repo.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this repository",
        )

    await repo_service.delete(repo)

    await audit_service.log_action(
        action="repository_deleted",
        entity_type="repository",
        entity_id=repo.id,
        user_id=current_user.id,
        details={"name": repo.name},
        request=request,
    )


@router.post("/{repository_id}/clone", response_model=RepositoryCloneResponse)
async def clone_repository(
    repository_id: uuid.UUID,
    current_user: CurrentUser,
    repo_service: RepoServiceDep,
    audit_service: AuditServiceDep,
    request: Request,
) -> RepositoryCloneResponse:
    """Clone a repository to local storage."""
    repo = await repo_service.get_by_id(repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    if repo.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to clone this repository",
        )

    try:
        local_path = await repo_service.clone(repo)

        await audit_service.log_repository_cloned(
            repository_id=repo.id,
            user_id=current_user.id,
            request=request,
        )

        return RepositoryCloneResponse(
            repository_id=repo.id,
            local_path=local_path,
            status="cloned",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clone repository: {str(e)}",
        )


@router.post("/{repository_id}/pull")
async def pull_repository(
    repository_id: uuid.UUID,
    current_user: CurrentUser,
    repo_service: RepoServiceDep,
) -> dict[str, str]:
    """Pull latest changes for a repository."""
    repo = await repo_service.get_by_id(repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    if repo.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to pull this repository",
        )

    if not repo.local_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository not cloned yet",
        )

    success = await repo_service.pull(repo)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to pull repository",
        )

    return {"status": "updated"}


@router.get("/{repository_id}/detect-version")
async def detect_jdk_version(
    repository_id: uuid.UUID,
    current_user: CurrentUser,
    repo_service: RepoServiceDep,
) -> dict[str, str | None]:
    """Detect JDK version from build files."""
    repo = await repo_service.get_by_id(repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    if repo.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this repository",
        )

    if not repo.local_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository not cloned yet",
        )

    version = await repo_service.detect_jdk_version(repo)
    return {"detected_version": version}
