"""Service for persisting agent results to database."""

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import Analysis, AnalysisStatus, ChangeType, Impact, RiskLevel
from app.models.audit import AnalysisHistory

logger = logging.getLogger(__name__)


class AgentPersistenceService:
    """Persists agent results to database for future reference."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_analysis_result(
        self,
        repository_id: uuid.UUID,
        user_id: uuid.UUID,
        from_version: str,
        to_version: str,
        agent_result: dict[str, Any],
        llm_provider: str | None = None,
    ) -> Analysis:
        """Save analysis result from agent to database."""
        logger.info(f"[Persistence] Saving analysis for repo {repository_id}")

        # Extract data from agent result
        data = agent_result.get("data", {})
        risk_score = data.get("risk_score", 0)
        risk_level_str = data.get("risk_level", "low")
        impacts_data = data.get("impacts", [])

        # Map risk level
        try:
            risk_level = RiskLevel(risk_level_str)
        except ValueError:
            risk_level = RiskLevel.LOW

        # Create analysis record
        analysis = Analysis(
            repository_id=repository_id,
            user_id=user_id,
            from_version=from_version,
            to_version=to_version,
            status=AnalysisStatus.COMPLETED,
            risk_score=risk_score,
            risk_level=risk_level,
            total_files_analyzed=data.get("total_files_analyzed", 0),
            summary=data.get("summary"),
            suggestions=data.get("suggestions"),
            llm_provider_used=llm_provider,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        self.db.add(analysis)
        await self.db.flush()  # Get the ID

        # Create impact records
        for impact_data in impacts_data:
            impact = self._create_impact_from_data(analysis.id, impact_data)
            self.db.add(impact)

        await self.db.commit()
        logger.info(f"[Persistence] Saved analysis {analysis.id} with {len(impacts_data)} impacts")

        # Also save to history
        await self._save_to_history(analysis, data)

        return analysis

    async def update_impacts_with_explanations(
        self,
        analysis_id: uuid.UUID,
        explained_impacts: list[dict[str, Any]],
    ) -> int:
        """Update impacts with LLM explanations."""
        logger.info(f"[Persistence] Updating explanations for analysis {analysis_id}")

        updated = 0
        for impact_data in explained_impacts:
            file_path = impact_data.get("file_path")
            line_number = impact_data.get("line_number")
            explanation = impact_data.get("llm_explanation")

            if file_path and explanation:
                # Find matching impacts (may be multiple per file)
                stmt = select(Impact).where(
                    Impact.analysis_id == analysis_id,
                    Impact.file_path == file_path,
                )
                if line_number:
                    stmt = stmt.where(Impact.line_number == line_number)

                result = await self.db.execute(stmt)
                impacts = result.scalars().all()

                for impact in impacts:
                    impact.llm_explanation = explanation
                    updated += 1

        await self.db.commit()
        logger.info(f"[Persistence] Updated {updated} impacts with explanations")
        return updated

    async def update_impacts_with_fixes(
        self,
        analysis_id: uuid.UUID,
        impacts_with_fixes: list[dict[str, Any]],
    ) -> int:
        """Update impacts with LLM-generated fixes."""
        logger.info(f"[Persistence] Updating fixes for analysis {analysis_id}")

        updated = 0
        for impact_data in impacts_with_fixes:
            file_path = impact_data.get("file_path")
            line_number = impact_data.get("line_number")
            fix = impact_data.get("fix")

            if file_path and fix:
                # Find matching impacts (may be multiple per file)
                stmt = select(Impact).where(
                    Impact.analysis_id == analysis_id,
                    Impact.file_path == file_path,
                )
                if line_number:
                    stmt = stmt.where(Impact.line_number == line_number)

                result = await self.db.execute(stmt)
                impacts = result.scalars().all()

                for impact in impacts:
                    impact.llm_fix = fix
                    updated += 1

        await self.db.commit()
        logger.info(f"[Persistence] Updated {updated} impacts with fixes")
        return updated

    async def update_impacts_with_patches(
        self,
        analysis_id: uuid.UUID,
        patches: list[dict[str, Any]],
    ) -> int:
        """Update impacts with patch content."""
        logger.info(f"[Persistence] Updating patches for analysis {analysis_id}")

        updated = 0
        for patch_data in patches:
            file_path = patch_data.get("file_path")
            patch_content = patch_data.get("patch", {})

            if file_path and patch_content:
                # Get patch content string
                if isinstance(patch_content, dict):
                    patch_str = patch_content.get("patch", str(patch_content))
                else:
                    patch_str = str(patch_content)

                # Update all impacts for this file
                stmt = select(Impact).where(
                    Impact.analysis_id == analysis_id,
                    Impact.file_path == file_path,
                )
                result = await self.db.execute(stmt)
                impacts = result.scalars().all()

                for impact in impacts:
                    impact.patch_content = patch_str
                    updated += 1

        await self.db.commit()
        logger.info(f"[Persistence] Updated {updated} impacts with patches")
        return updated

    async def get_analysis_with_impacts(
        self,
        analysis_id: uuid.UUID,
    ) -> Analysis | None:
        """Get analysis with all impacts."""
        stmt = select(Analysis).where(Analysis.id == analysis_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_impacts_for_agent(
        self,
        analysis_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Get impacts as dicts suitable for agent processing."""
        analysis = await self.get_analysis_with_impacts(analysis_id)
        if not analysis:
            return []

        impacts_data = []
        for impact in analysis.impacts:
            impacts_data.append({
                "file_path": impact.file_path,
                "line_number": impact.line_number,
                "change_type": impact.change_type.value if impact.change_type else None,
                "severity": impact.severity.value if impact.severity else None,
                "code_snippet": impact.affected_code,
                "description": impact.description,
                "affected_class": impact.affected_class,
                "affected_method": impact.affected_method,
                "cve_id": impact.cve_id,
                "suggested_fix": impact.suggested_fix,
                "llm_explanation": impact.llm_explanation,
                "fix": impact.llm_fix,
            })
        return impacts_data

    async def get_latest_analysis(
        self,
        repository_id: uuid.UUID,
    ) -> Analysis | None:
        """Get the most recent analysis for a repository."""
        stmt = (
            select(Analysis)
            .where(Analysis.repository_id == repository_id)
            .order_by(Analysis.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    def _create_impact_from_data(
        self,
        analysis_id: uuid.UUID,
        data: dict[str, Any],
    ) -> Impact:
        """Create Impact model from data dict."""
        # Map change type
        change_type_str = data.get("change_type", "bugfix")
        try:
            change_type = ChangeType(change_type_str)
        except ValueError:
            change_type = ChangeType.BUGFIX

        # Map severity
        severity_str = data.get("severity", "low")
        try:
            severity = RiskLevel(severity_str)
        except ValueError:
            severity = RiskLevel.LOW

        return Impact(
            analysis_id=analysis_id,
            file_path=data.get("file_path", ""),
            line_number=data.get("line_number"),
            change_type=change_type,
            severity=severity,
            affected_code=data.get("code_snippet"),
            description=data.get("description", ""),
            affected_class=data.get("affected_class"),
            affected_method=data.get("affected_method"),
            cve_id=data.get("cve_id"),
            suggested_fix=data.get("suggested_fix"),
            llm_explanation=data.get("llm_explanation"),
            llm_fix=data.get("fix"),
        )

    async def _save_to_history(
        self,
        analysis: Analysis,
        full_data: dict[str, Any],
    ) -> None:
        """Save analysis to history table (never deleted)."""
        impacts = full_data.get("impacts", [])

        # Count by severity
        high_count = sum(1 for i in impacts if i.get("severity") in ["high", "critical"])
        medium_count = sum(1 for i in impacts if i.get("severity") == "medium")
        low_count = sum(1 for i in impacts if i.get("severity") == "low")

        history = AnalysisHistory(
            analysis_id=analysis.id,
            repository_id=analysis.repository_id,
            user_id=analysis.user_id,
            from_version=analysis.from_version,
            to_version=analysis.to_version,
            risk_score=analysis.risk_score,
            risk_level=analysis.risk_level.value if analysis.risk_level else None,
            total_impacts=len(impacts),
            high_severity_count=high_count,
            medium_severity_count=medium_count,
            low_severity_count=low_count,
            full_report=full_data,
        )
        self.db.add(history)
        await self.db.commit()
        logger.info(f"[Persistence] Saved to history: {history.id}")
