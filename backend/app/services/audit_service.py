"""Service for audit logging and history management."""

import uuid
from datetime import datetime

from fastapi import Request
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import Analysis, RiskLevel
from app.models.audit import AnalysisHistory, AuditLog
from app.schemas.audit import AnalysisHistoryQuery, AuditLogQuery


class AuditService:
    """Service for audit logging and history tracking."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_action(
        self,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        details: dict | None = None,
        request: Request | None = None,
    ) -> AuditLog:
        """Log an action to the audit trail."""
        ip_address = None
        user_agent = None

        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")

        audit_entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.db.add(audit_entry)
        await self.db.commit()
        await self.db.refresh(audit_entry)

        return audit_entry

    async def save_analysis_history(
        self,
        analysis: Analysis,
        full_report: dict | None = None,
    ) -> AnalysisHistory:
        """Archive a completed analysis for historical records."""
        # Count impacts by severity
        high_count = sum(
            1 for impact in analysis.impacts if impact.severity == RiskLevel.HIGH
        )
        medium_count = sum(
            1 for impact in analysis.impacts if impact.severity == RiskLevel.MEDIUM
        )
        low_count = sum(
            1 for impact in analysis.impacts if impact.severity == RiskLevel.LOW
        )
        critical_count = sum(
            1 for impact in analysis.impacts if impact.severity == RiskLevel.CRITICAL
        )

        history = AnalysisHistory(
            analysis_id=analysis.id,
            repository_id=analysis.repository_id,
            user_id=analysis.user_id,
            from_version=analysis.from_version,
            to_version=analysis.to_version,
            risk_score=analysis.risk_score,
            risk_level=analysis.risk_level,
            total_impacts=len(analysis.impacts),
            high_severity_count=high_count + critical_count,
            medium_severity_count=medium_count,
            low_severity_count=low_count,
            full_report=full_report,
        )

        self.db.add(history)
        await self.db.commit()
        await self.db.refresh(history)

        return history

    async def get_audit_trail(
        self,
        query: AuditLogQuery,
    ) -> list[AuditLog]:
        """Query audit log with filters."""
        conditions = []

        if query.entity_type:
            conditions.append(AuditLog.entity_type == query.entity_type)
        if query.entity_id:
            conditions.append(AuditLog.entity_id == query.entity_id)
        if query.user_id:
            conditions.append(AuditLog.user_id == query.user_id)
        if query.action:
            conditions.append(AuditLog.action == query.action)
        if query.start_date:
            conditions.append(AuditLog.created_at >= query.start_date)
        if query.end_date:
            conditions.append(AuditLog.created_at <= query.end_date)

        stmt = (
            select(AuditLog)
            .where(and_(*conditions) if conditions else True)
            .order_by(AuditLog.created_at.desc())
            .offset(query.offset)
            .limit(query.limit)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_analysis_history(
        self,
        query: AnalysisHistoryQuery,
    ) -> list[AnalysisHistory]:
        """Query analysis history with filters."""
        conditions = []

        if query.repository_id:
            conditions.append(AnalysisHistory.repository_id == query.repository_id)
        if query.user_id:
            conditions.append(AnalysisHistory.user_id == query.user_id)
        if query.from_version:
            conditions.append(AnalysisHistory.from_version == query.from_version)
        if query.to_version:
            conditions.append(AnalysisHistory.to_version == query.to_version)
        if query.start_date:
            conditions.append(AnalysisHistory.created_at >= query.start_date)
        if query.end_date:
            conditions.append(AnalysisHistory.created_at <= query.end_date)

        stmt = (
            select(AnalysisHistory)
            .where(and_(*conditions) if conditions else True)
            .order_by(AnalysisHistory.created_at.desc())
            .offset(query.offset)
            .limit(query.limit)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_analysis_history_by_id(
        self,
        history_id: uuid.UUID,
    ) -> AnalysisHistory | None:
        """Get a specific analysis history entry."""
        result = await self.db.execute(
            select(AnalysisHistory).where(AnalysisHistory.id == history_id)
        )
        return result.scalar_one_or_none()

    async def get_repository_history(
        self,
        repository_id: uuid.UUID,
        limit: int = 10,
    ) -> list[AnalysisHistory]:
        """Get analysis history for a specific repository."""
        stmt = (
            select(AnalysisHistory)
            .where(AnalysisHistory.repository_id == repository_id)
            .order_by(AnalysisHistory.created_at.desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_user_activity(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
    ) -> list[AuditLog]:
        """Get recent activity for a user."""
        stmt = (
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def log_login(
        self,
        user_id: uuid.UUID,
        auth_method: str,
        request: Request | None = None,
        success: bool = True,
    ) -> AuditLog:
        """Log a login attempt."""
        return await self.log_action(
            action="login_success" if success else "login_failed",
            entity_type="user",
            entity_id=user_id,
            user_id=user_id if success else None,
            details={"auth_method": auth_method},
            request=request,
        )

    async def log_analysis_started(
        self,
        analysis: Analysis,
        request: Request | None = None,
    ) -> AuditLog:
        """Log when an analysis is started."""
        return await self.log_action(
            action="analysis_started",
            entity_type="analysis",
            entity_id=analysis.id,
            user_id=analysis.user_id,
            details={
                "repository_id": str(analysis.repository_id),
                "from_version": analysis.from_version,
                "to_version": analysis.to_version,
            },
            request=request,
        )

    async def log_analysis_completed(
        self,
        analysis: Analysis,
        request: Request | None = None,
    ) -> AuditLog:
        """Log when an analysis is completed."""
        return await self.log_action(
            action="analysis_completed",
            entity_type="analysis",
            entity_id=analysis.id,
            user_id=analysis.user_id,
            details={
                "repository_id": str(analysis.repository_id),
                "from_version": analysis.from_version,
                "to_version": analysis.to_version,
                "risk_score": analysis.risk_score,
                "risk_level": analysis.risk_level,
                "total_impacts": len(analysis.impacts),
            },
            request=request,
        )

    async def log_repository_cloned(
        self,
        repository_id: uuid.UUID,
        user_id: uuid.UUID,
        request: Request | None = None,
    ) -> AuditLog:
        """Log when a repository is cloned."""
        return await self.log_action(
            action="repository_cloned",
            entity_type="repository",
            entity_id=repository_id,
            user_id=user_id,
            request=request,
        )
