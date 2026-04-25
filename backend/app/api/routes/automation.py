"""Automation routes for Renovate-style operations."""

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession
from app.services.audit_service import AuditService
from app.services.renovate_service import RenovateService, renovate_service
from app.services.repository_service import RepositoryService

router = APIRouter()


class VersionBumpRequest(BaseModel):
    """Request to generate or apply version bump."""

    target_version: str


class VersionBumpResponse(BaseModel):
    """Response with version bump details."""

    file_path: str
    old_version: str
    new_version: str
    line_number: int
    diff: str


class PatchInfo(BaseModel):
    """Available patch information."""

    version: str
    release_date: str
    release_type: str
    download_url: str | None
    release_notes_url: str | None
    security_fixes: list[str]
    is_lts: bool


class CurrentVersionResponse(BaseModel):
    """Current JDK version information."""

    major: int
    minor: int
    patch: int
    full: str
    source_file: str
    source_line: int | None


async def get_repository_service(db: DbSession) -> RepositoryService:
    return RepositoryService(db)


async def get_audit_service(db: DbSession) -> AuditService:
    return AuditService(db)


RepoServiceDep = Annotated[RepositoryService, Depends(get_repository_service)]
AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]


@router.get("/{repository_id}/jdk-version", response_model=CurrentVersionResponse | None)
async def get_jdk_version(
    repository_id: uuid.UUID,
    current_user: CurrentUser,
    repo_service: RepoServiceDep,
):
    """Detect current JDK version from repository build files."""
    repo = await repo_service.get_by_id(repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if not repo.local_path:
        raise HTTPException(status_code=400, detail="Repository not cloned")

    version = await renovate_service.detect_jdk_version(Path(repo.local_path))
    if not version:
        return None

    return CurrentVersionResponse(
        major=version.major,
        minor=version.minor,
        patch=version.patch,
        full=version.full,
        source_file=version.source_file,
        source_line=version.source_line,
    )


@router.get("/{repository_id}/available-patches", response_model=list[PatchInfo])
async def get_available_patches(
    repository_id: uuid.UUID,
    current_user: CurrentUser,
    repo_service: RepoServiceDep,
):
    """Get available JDK patch versions for the repository."""
    repo = await repo_service.get_by_id(repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if not repo.local_path:
        raise HTTPException(status_code=400, detail="Repository not cloned")

    current = await renovate_service.detect_jdk_version(Path(repo.local_path))
    if not current:
        raise HTTPException(status_code=400, detail="Could not detect JDK version")

    patches = await renovate_service.get_available_patches(current)

    return [
        PatchInfo(
            version=p.version,
            release_date=p.release_date,
            release_type=p.release_type,
            download_url=p.download_url,
            release_notes_url=p.release_notes_url,
            security_fixes=p.security_fixes,
            is_lts=p.is_lts,
        )
        for p in patches
    ]


@router.post("/{repository_id}/preview-bump", response_model=list[VersionBumpResponse])
async def preview_version_bump(
    repository_id: uuid.UUID,
    request: VersionBumpRequest,
    current_user: CurrentUser,
    repo_service: RepoServiceDep,
):
    """Preview version bump changes without applying them."""
    repo = await repo_service.get_by_id(repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if not repo.local_path:
        raise HTTPException(status_code=400, detail="Repository not cloned")

    bumps = await renovate_service.generate_version_bump(
        Path(repo.local_path),
        request.target_version,
    )

    return [
        VersionBumpResponse(
            file_path=b.file_path,
            old_version=b.old_version,
            new_version=b.new_version,
            line_number=b.line_number,
            diff=b.diff,
        )
        for b in bumps
    ]


@router.post("/{repository_id}/apply-bump", response_model=list[VersionBumpResponse])
async def apply_version_bump(
    repository_id: uuid.UUID,
    request: VersionBumpRequest,
    current_user: CurrentUser,
    repo_service: RepoServiceDep,
    audit_service: AuditServiceDep,
    http_request: Request,
):
    """Apply version bump to repository files."""
    repo = await repo_service.get_by_id(repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if not repo.local_path:
        raise HTTPException(status_code=400, detail="Repository not cloned")

    bumps = await renovate_service.generate_version_bump(
        Path(repo.local_path),
        request.target_version,
    )

    applied = []
    for bump in bumps:
        success = await renovate_service.apply_version_bump(bump)
        if success:
            applied.append(bump)

    # Log the action
    await audit_service.log_action(
        action="version_bump_applied",
        entity_type="repository",
        entity_id=repository_id,
        user_id=current_user.id,
        details={
            "target_version": request.target_version,
            "files_updated": [b.file_path for b in applied],
        },
        request=http_request,
    )

    return [
        VersionBumpResponse(
            file_path=b.file_path,
            old_version=b.old_version,
            new_version=b.new_version,
            line_number=b.line_number,
            diff=b.diff,
        )
        for b in applied
    ]


@router.post("/{repository_id}/generate-renovate-config")
async def generate_renovate_config(
    repository_id: uuid.UUID,
    current_user: CurrentUser,
    repo_service: RepoServiceDep,
    target_jdk: str | None = None,
):
    """Generate a renovate.json configuration for the repository."""
    repo = await repo_service.get_by_id(repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if not repo.local_path:
        raise HTTPException(status_code=400, detail="Repository not cloned")

    config = await renovate_service.generate_renovate_config(
        Path(repo.local_path),
        target_jdk,
    )

    return {"config": config}


@router.post("/{repository_id}/save-renovate-config")
async def save_renovate_config(
    repository_id: uuid.UUID,
    current_user: CurrentUser,
    repo_service: RepoServiceDep,
    audit_service: AuditServiceDep,
    http_request: Request,
    target_jdk: str | None = None,
):
    """Generate and save renovate.json to the repository."""
    repo = await repo_service.get_by_id(repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if not repo.local_path:
        raise HTTPException(status_code=400, detail="Repository not cloned")

    config = await renovate_service.generate_renovate_config(
        Path(repo.local_path),
        target_jdk,
    )
    config_path = await renovate_service.save_renovate_config(
        Path(repo.local_path),
        config,
    )

    await audit_service.log_action(
        action="renovate_config_created",
        entity_type="repository",
        entity_id=repository_id,
        user_id=current_user.id,
        details={"config_path": config_path},
        request=http_request,
    )

    return {"config_path": config_path, "config": config}
