"""Service for analyzing Java code for JDK upgrade impacts using tree-sitter."""

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from app.models.analysis import AnalysisStatus, ChangeType, RiskLevel
from app.services.llm_service import LLMService, llm_service
from app.services.release_notes_service import JDKChange, release_notes_service

logger = logging.getLogger(__name__)


@dataclass
class CodeLocation:
    """Location of code in a file."""

    file_path: str
    line_number: int
    column_number: int
    code_snippet: str


@dataclass
class ImpactItem:
    """A single impact found in the code."""

    location: CodeLocation
    change: JDKChange
    severity: RiskLevel
    affected_class: str | None
    affected_method: str | None
    suggested_fix: str | None = None


@dataclass
class AnalysisResult:
    """Result of a complete analysis."""

    status: AnalysisStatus
    impacts: list[ImpactItem]
    risk_score: int
    risk_level: RiskLevel
    total_files_analyzed: int
    summary: str | None
    suggestions: dict | None
    error_message: str | None = None


class AnalyzerService:
    """Service for analyzing Java code for JDK upgrade impacts."""

    def __init__(self, llm: LLMService | None = None):
        self.llm = llm or llm_service
        self._parser: Parser | None = None
        self._language: Language | None = None

    def _get_parser(self) -> Parser:
        """Get or create the tree-sitter parser."""
        if self._parser is None:
            self._language = Language(tsjava.language())
            self._parser = Parser(self._language)
        return self._parser

    async def analyze_repository(
        self,
        repo_path: Path,
        from_version: str,
        to_version: str,
        llm_provider: str | None = None,
    ) -> AnalysisResult:
        """Analyze a repository for JDK upgrade impacts."""
        try:
            # 1. Scan for Java files
            logger.info(f"[Analyzer] Scanning for Java files in {repo_path}")
            java_files = await self._scan_java_files(repo_path)
            logger.info(f"[Analyzer] Found {len(java_files)} Java files")

            if not java_files:
                return AnalysisResult(
                    status=AnalysisStatus.COMPLETED,
                    impacts=[],
                    risk_score=0,
                    risk_level=RiskLevel.LOW,
                    total_files_analyzed=0,
                    summary="No Java files found in repository",
                    suggestions=None,
                )

            # 2. Fetch release notes for version range
            logger.info(f"[Analyzer] Fetching release notes: {from_version} -> {to_version}")
            changes = await release_notes_service.get_changes_between_versions(
                from_version,
                to_version,
            )
            logger.info(f"[Analyzer] Got {len(changes)} JDK changes to check against")

            # 3. Analyze each file for impacts
            logger.info("[Analyzer] Analyzing files for impacts...")
            all_impacts: list[ImpactItem] = []
            for file_path in java_files:
                file_impacts = await self._analyze_file(file_path, changes)
                if file_impacts:
                    logger.info(f"[Analyzer] {file_path.name}: {len(file_impacts)} impacts")
                all_impacts.extend(file_impacts)

            logger.info(f"[Analyzer] Total impacts found: {len(all_impacts)}")

            # 4. Calculate risk score
            risk_score, risk_level = self._calculate_risk_score(all_impacts)
            logger.info(f"[Analyzer] Risk score: {risk_score}, level: {risk_level}")

            # 5. Generate suggestions using LLM (if available)
            summary = None
            suggestions = None
            if all_impacts and self.llm.available_providers:
                logger.info("[Analyzer] Generating LLM suggestions...")
                try:
                    summary, suggestions = await self._generate_suggestions(
                        all_impacts,
                        from_version,
                        to_version,
                        llm_provider,
                    )
                    logger.info("[Analyzer] LLM suggestions generated")
                except Exception as e:
                    logger.warning(f"[Analyzer] LLM suggestion failed: {e}")

            logger.info("[Analyzer] Analysis complete")
            return AnalysisResult(
                status=AnalysisStatus.COMPLETED,
                impacts=all_impacts,
                risk_score=risk_score,
                risk_level=risk_level,
                total_files_analyzed=len(java_files),
                summary=summary,
                suggestions=suggestions,
            )

        except Exception as e:
            logger.error(f"[Analyzer] Analysis failed: {e}")
            return AnalysisResult(
                status=AnalysisStatus.FAILED,
                impacts=[],
                risk_score=0,
                risk_level=RiskLevel.LOW,
                total_files_analyzed=0,
                summary=None,
                suggestions=None,
                error_message=str(e),
            )

    async def _scan_java_files(self, repo_path: Path) -> list[Path]:
        """Scan repository for Java files."""
        java_files: list[Path] = []

        # Use asyncio to avoid blocking
        def scan():
            return list(repo_path.rglob("*.java"))

        loop = asyncio.get_event_loop()
        java_files = await loop.run_in_executor(None, scan)

        # Filter out test files and generated code
        filtered = [
            f
            for f in java_files
            if not any(
                part in str(f)
                for part in ["/test/", "/tests/", "/generated/", "/target/", "/build/"]
            )
        ]

        return filtered

    async def _analyze_file(
        self,
        file_path: Path,
        changes: list[JDKChange],
    ) -> list[ImpactItem]:
        """Analyze a single Java file for impacts."""
        impacts: list[ImpactItem] = []

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            return impacts

        # Parse the file with tree-sitter
        parser = self._get_parser()
        tree = parser.parse(content.encode())

        # Extract imports, class usages, and method calls
        imports = self._extract_imports(tree, content)
        usages = self._extract_usages(tree, content)

        # Match against changes
        for change in changes:
            # Check imports
            for imp in imports:
                if self._matches_change(imp["name"], change):
                    impacts.append(
                        ImpactItem(
                            location=CodeLocation(
                                file_path=str(file_path),
                                line_number=imp["line"],
                                column_number=imp["column"],
                                code_snippet=imp["code"],
                            ),
                            change=change,
                            severity=self._get_severity(change),
                            affected_class=imp["name"],
                            affected_method=None,
                        )
                    )

            # Check usages
            for usage in usages:
                if self._matches_change(usage["name"], change):
                    impacts.append(
                        ImpactItem(
                            location=CodeLocation(
                                file_path=str(file_path),
                                line_number=usage["line"],
                                column_number=usage["column"],
                                code_snippet=usage["code"],
                            ),
                            change=change,
                            severity=self._get_severity(change),
                            affected_class=usage.get("class"),
                            affected_method=usage.get("method"),
                        )
                    )

        # Deduplicate impacts by (file, line, affected_class/method)
        seen = set()
        unique_impacts = []
        for impact in impacts:
            key = (
                impact.location.file_path,
                impact.location.line_number,
                impact.affected_class or "",
                impact.affected_method or "",
            )
            if key not in seen:
                seen.add(key)
                unique_impacts.append(impact)

        return unique_impacts

    def _extract_imports(self, tree, content: str) -> list[dict]:
        """Extract import statements from AST."""
        imports = []

        def visit(node):
            if node.type == "import_declaration":
                # Get the import name
                for child in node.children:
                    if child.type == "scoped_identifier":
                        name = content[child.start_byte : child.end_byte]
                        imports.append({
                            "name": name,
                            "line": node.start_point[0] + 1,
                            "column": node.start_point[1],
                            "code": content[node.start_byte : node.end_byte],
                        })
            for child in node.children:
                visit(child)

        visit(tree.root_node)
        return imports

    def _extract_usages(self, tree, content: str) -> list[dict]:
        """Extract class and method usages from AST."""
        usages = []

        def visit(node):
            # Method invocations
            if node.type == "method_invocation":
                method_name = None
                class_name = None

                for child in node.children:
                    if child.type == "identifier":
                        method_name = content[child.start_byte : child.end_byte]
                    elif child.type == "field_access":
                        class_name = content[child.start_byte : child.end_byte]

                if method_name:
                    usages.append({
                        "name": f"{class_name}.{method_name}" if class_name else method_name,
                        "line": node.start_point[0] + 1,
                        "column": node.start_point[1],
                        "code": content[node.start_byte : node.end_byte][:100],
                        "class": class_name,
                        "method": method_name,
                    })

            # Type references (class instantiation, variable declarations)
            elif node.type == "type_identifier":
                type_name = content[node.start_byte : node.end_byte]
                usages.append({
                    "name": type_name,
                    "line": node.start_point[0] + 1,
                    "column": node.start_point[1],
                    "code": content[
                        max(0, node.start_byte - 20) : min(len(content), node.end_byte + 20)
                    ],
                    "class": type_name,
                    "method": None,
                })

            for child in node.children:
                visit(child)

        visit(tree.root_node)
        return usages

    def _matches_change(self, usage_name: str, change: JDKChange) -> bool:
        """Check if a usage matches a JDK change."""
        # Skip overly generic names that cause false positives
        GENERIC_NAMES = {
            "String", "Object", "Integer", "Long", "Boolean", "Double", "Float",
            "List", "Map", "Set", "Collection", "Array", "Class", "System",
            "Exception", "Error", "Throwable", "Thread", "Runnable",
        }
        if usage_name in GENERIC_NAMES:
            return False

        # Check against affected classes
        for affected_class in change.affected_classes:
            # Skip if the affected class is generic
            simple_name = affected_class.split(".")[-1]
            if simple_name in GENERIC_NAMES:
                continue

            # Exact match (fully qualified)
            if usage_name == affected_class:
                return True
            # Simple name match only if it's a specific class
            if usage_name == simple_name and len(simple_name) > 3:
                return True
            # Package-qualified match
            if usage_name.endswith(f".{simple_name}") or usage_name.startswith(f"{simple_name}."):
                return True

        # Check against affected methods (more strict)
        for affected_method in change.affected_methods:
            # Require exact method name match, not substring
            method_simple = affected_method.split(".")[-1] if "." in affected_method else affected_method
            if method_simple in GENERIC_NAMES:
                continue
            # Match method call pattern: Class.method or just method
            if usage_name == affected_method or usage_name.endswith(f".{method_simple}"):
                return True

        return False

    def _get_severity(self, change: JDKChange) -> RiskLevel:
        """Determine severity based on change type."""
        if change.change_type == ChangeType.REMOVED:
            return RiskLevel.CRITICAL
        elif change.change_type == ChangeType.SECURITY:
            return RiskLevel.HIGH
        elif change.change_type == ChangeType.BEHAVIORAL:
            return RiskLevel.MEDIUM
        elif change.change_type == ChangeType.DEPRECATED:
            return RiskLevel.LOW
        else:
            return RiskLevel.LOW

    def _calculate_risk_score(
        self,
        impacts: list[ImpactItem],
    ) -> tuple[int, RiskLevel]:
        """Calculate overall risk score from impacts."""
        if not impacts:
            return 0, RiskLevel.LOW

        score = 0
        for impact in impacts:
            if impact.change.change_type == ChangeType.REMOVED:
                score += 30  # Critical - will break
            elif impact.change.change_type == ChangeType.SECURITY:
                score += 15  # Should address
            elif impact.change.change_type == ChangeType.BEHAVIORAL:
                score += 20  # May cause subtle bugs
            elif impact.change.change_type == ChangeType.DEPRECATED:
                score += 10  # Warning

        # Cap at 100
        score = min(score, 100)

        # Determine risk level
        if score >= 70:
            risk_level = RiskLevel.CRITICAL
        elif score >= 40:
            risk_level = RiskLevel.HIGH
        elif score >= 20:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        return score, risk_level

    async def _generate_suggestions(
        self,
        impacts: list[ImpactItem],
        from_version: str,
        to_version: str,
        llm_provider: str | None,
    ) -> tuple[str, dict]:
        """Generate suggestions using LLM."""
        # Prepare impacts for LLM
        impacts_data = [
            {
                "file_path": impact.location.file_path,
                "line_number": impact.location.line_number,
                "description": impact.change.description,
                "change_type": impact.change.change_type,
                "severity": impact.severity,
                "affected_class": impact.affected_class,
                "code_snippet": impact.location.code_snippet,
            }
            for impact in impacts[:20]  # Limit to avoid token limits
        ]

        # Generate migration plan
        migration_plan = await self.llm.generate_migration_plan(
            impacts_data,
            from_version,
            to_version,
            llm_provider,
        )

        # Parse suggestions from the plan
        suggestions = {
            "migration_plan": migration_plan,
            "high_priority_fixes": [
                i for i in impacts_data if i["severity"] in [RiskLevel.CRITICAL, RiskLevel.HIGH]
            ],
            "total_impacts": len(impacts),
        }

        # Generate a brief summary
        summary = f"Analysis found {len(impacts)} potential impacts when upgrading from JDK {from_version} to {to_version}. "
        critical_count = sum(1 for i in impacts if i.severity == RiskLevel.CRITICAL)
        high_count = sum(1 for i in impacts if i.severity == RiskLevel.HIGH)

        if critical_count > 0:
            summary += f"{critical_count} critical issues require immediate attention. "
        if high_count > 0:
            summary += f"{high_count} high-severity issues should be addressed before upgrade."

        return summary, suggestions


# Global instance
analyzer_service = AnalyzerService()
