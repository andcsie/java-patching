"""Impact analysis routes."""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.models.analysis import Analysis, AnalysisStatus, Impact, RiskLevel
from app.schemas.analysis import AnalysisCreate, AnalysisResponse, AnalysisSummary
from app.services.analyzer_service import AnalyzerService, analyzer_service
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


@router.post("/analyze", response_model=AnalysisResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_analysis(
    analysis_data: AnalysisCreate,
    current_user: CurrentUser,
    db: DbSession,
    repo_service: RepoServiceDep,
    audit_service: AuditServiceDep,
    background_tasks: BackgroundTasks,
    request: Request,
) -> AnalysisResponse:
    """Start a new impact analysis for a repository."""
    # Verify repository exists and user has access
    repo = await repo_service.get_by_id(analysis_data.repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    if repo.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to analyze this repository",
        )

    if not repo.local_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository not cloned yet. Clone it first.",
        )

    # Create analysis record
    analysis = Analysis(
        repository_id=analysis_data.repository_id,
        user_id=current_user.id,
        from_version=analysis_data.from_version,
        to_version=analysis_data.to_version,
        status=AnalysisStatus.PENDING,
        llm_provider_used=analysis_data.llm_provider,
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    # Log analysis started
    await audit_service.log_analysis_started(analysis, request)

    # Run analysis in background
    background_tasks.add_task(
        run_analysis_background,
        db,
        analysis.id,
        repo.local_path,
        analysis_data.from_version,
        analysis_data.to_version,
        analysis_data.llm_provider,
    )

    return AnalysisResponse.model_validate(analysis)


async def run_analysis_background(
    db: AsyncSession,
    analysis_id: uuid.UUID,
    repo_path: str,
    from_version: str,
    to_version: str,
    llm_provider: str | None,
) -> None:
    """Run analysis in background."""
    # Get analysis
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if not analysis:
        return

    # Update status to running
    analysis.status = AnalysisStatus.RUNNING
    analysis.started_at = datetime.now(UTC)
    await db.commit()

    try:
        # Run the analysis
        result = await analyzer_service.analyze_repository(
            repo_path=Path(repo_path),
            from_version=from_version,
            to_version=to_version,
            llm_provider=llm_provider,
        )

        # Update analysis with results
        analysis.status = result.status
        analysis.risk_score = result.risk_score
        analysis.risk_level = result.risk_level
        analysis.total_files_analyzed = result.total_files_analyzed
        analysis.summary = result.summary
        analysis.suggestions = result.suggestions
        analysis.error_message = result.error_message
        analysis.completed_at = datetime.now(UTC)

        # Create impact records
        for impact_item in result.impacts:
            impact = Impact(
                analysis_id=analysis.id,
                file_path=impact_item.location.file_path,
                line_number=impact_item.location.line_number,
                column_number=impact_item.location.column_number,
                change_type=impact_item.change.change_type,
                severity=impact_item.severity,
                affected_code=impact_item.location.code_snippet,
                description=impact_item.change.description,
                affected_class=impact_item.affected_class,
                affected_method=impact_item.affected_method,
                jdk_component=impact_item.change.component,
                cve_id=impact_item.change.cve_id,
                migration_notes=impact_item.change.migration_notes,
                suggested_fix=impact_item.suggested_fix,
            )
            db.add(impact)

        await db.commit()

        # Save to analysis history
        audit_service = AuditService(db)
        await audit_service.save_analysis_history(
            analysis,
            full_report={
                "impacts": [
                    {
                        "file_path": i.location.file_path,
                        "line_number": i.location.line_number,
                        "change_type": i.change.change_type,
                        "severity": i.severity,
                        "description": i.change.description,
                    }
                    for i in result.impacts
                ],
                "summary": result.summary,
                "suggestions": result.suggestions,
            },
        )

    except Exception as e:
        analysis.status = AnalysisStatus.FAILED
        analysis.error_message = str(e)
        analysis.completed_at = datetime.now(UTC)
        await db.commit()


@router.get("/analyses", response_model=list[AnalysisSummary])
async def list_analyses(
    current_user: CurrentUser,
    db: DbSession,
    repository_id: uuid.UUID | None = None,
    limit: int = 20,
) -> list[AnalysisSummary]:
    """List analyses for the current user."""
    stmt = select(Analysis).where(Analysis.user_id == current_user.id)

    if repository_id:
        stmt = stmt.where(Analysis.repository_id == repository_id)

    stmt = stmt.order_by(Analysis.created_at.desc()).limit(limit)

    result = await db.execute(stmt)
    analyses = result.scalars().all()

    summaries = []
    for a in analyses:
        impacts = a.impacts if a.impacts else []
        summaries.append(
            AnalysisSummary(
                id=a.id,
                repository_id=a.repository_id,
                from_version=a.from_version,
                to_version=a.to_version,
                status=a.status,
                risk_score=a.risk_score,
                risk_level=a.risk_level,
                total_impacts=len(impacts),
                high_severity_count=sum(
                    1 for i in impacts if i.severity in [RiskLevel.HIGH, RiskLevel.CRITICAL]
                ),
                medium_severity_count=sum(1 for i in impacts if i.severity == RiskLevel.MEDIUM),
                low_severity_count=sum(1 for i in impacts if i.severity == RiskLevel.LOW),
                created_at=a.created_at,
            )
        )

    return summaries


@router.get("/analyses/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> AnalysisResponse:
    """Get a specific analysis with all impacts."""
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    analysis = result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )

    if analysis.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this analysis",
        )

    return AnalysisResponse.model_validate(analysis)


@router.delete("/analyses/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_analysis(
    analysis_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete an analysis."""
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    analysis = result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )

    if analysis.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this analysis",
        )

    await db.delete(analysis)
    await db.commit()
