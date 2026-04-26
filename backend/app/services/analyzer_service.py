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
        skip_llm: bool = False,
    ) -> AnalysisResult:
        """Analyze a repository for JDK upgrade impacts using Code + Release Notes + LLM."""
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

            # 2. Fetch release notes for version range (for context)
            logger.info(f"[Analyzer] Fetching release notes: {from_version} -> {to_version}")
            release_notes_changes = await release_notes_service.get_changes_between_versions(
                from_version,
                to_version,
            )
            logger.info(f"[Analyzer] Got {len(release_notes_changes)} changes from release notes")

            # 3. Analyze each file using LLM (Code + Release Notes + LLM)
            logger.info("[Analyzer] Analyzing files with LLM...")
            all_impacts: list[ImpactItem] = []

            if skip_llm or not self.llm.available_providers:
                # Fallback: basic AST matching only
                logger.info("[Analyzer] LLM skipped - using AST matching only")
                for file_path in java_files:
                    file_impacts = await self._analyze_file_basic(file_path, release_notes_changes)
                    all_impacts.extend(file_impacts)
            else:
                # Full analysis: send code to LLM with release notes context
                for file_path in java_files:
                    file_impacts = await self._analyze_file_with_llm(
                        file_path,
                        from_version,
                        to_version,
                        release_notes_changes,
                        llm_provider,
                    )
                    if file_impacts:
                        logger.info(f"[Analyzer] {file_path.name}: {len(file_impacts)} impacts")
                    all_impacts.extend(file_impacts)

            logger.info(f"[Analyzer] Total impacts found: {len(all_impacts)}")

            # 4. Calculate risk score
            risk_score, risk_level = self._calculate_risk_score(all_impacts)
            logger.info(f"[Analyzer] Risk score: {risk_score}, level: {risk_level}")

            # 5. Generate summary
            summary = f"Found {len(all_impacts)} potential compatibility issues upgrading from JDK {from_version} to {to_version}."

            logger.info("[Analyzer] Analysis complete")
            return AnalysisResult(
                status=AnalysisStatus.COMPLETED,
                impacts=all_impacts,
                risk_score=risk_score,
                risk_level=risk_level,
                total_files_analyzed=len(java_files),
                summary=summary,
                suggestions=None,
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

    async def _analyze_file_with_llm(
        self,
        file_path: Path,
        from_version: str,
        to_version: str,
        release_notes_changes: list[JDKChange],
        llm_provider: str | None,
    ) -> list[ImpactItem]:
        """Analyze a file using LLM with code + release notes context (Hybrid approach)."""
        import json

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            return []

        # Truncate large files
        lines = content.split('\n')
        if len(lines) > 150:
            content = '\n'.join(lines[:150]) + f"\n... ({len(lines) - 150} more lines)"

        # Build release notes context - group by type for clarity
        release_context = ""
        if release_notes_changes:
            security_changes = [c for c in release_notes_changes if c.change_type == ChangeType.SECURITY]
            behavioral_changes = [c for c in release_notes_changes if c.change_type == ChangeType.BEHAVIORAL]
            other_changes = [c for c in release_notes_changes if c.change_type not in (ChangeType.SECURITY, ChangeType.BEHAVIORAL)]

            parts = []
            if security_changes:
                parts.append("Security fixes:\n" + "\n".join(f"- {c.description[:150]}" for c in security_changes[:5]))
            if behavioral_changes:
                parts.append("Behavioral changes:\n" + "\n".join(f"- {c.description[:150]}" for c in behavioral_changes[:5]))
            if other_changes[:3]:
                parts.append("Other changes:\n" + "\n".join(f"- {c.description[:100]}" for c in other_changes[:3]))

            if parts:
                release_context = "\n\n".join(parts)
                logger.info(f"[Analyzer] Release notes context: {len(security_changes)} security, {len(behavioral_changes)} behavioral, {len(other_changes)} other")
            else:
                logger.info("[Analyzer] No release notes - LLM will use its knowledge only")
        else:
            logger.info("[Analyzer] No release notes fetched - LLM will use its knowledge only")

        # Hybrid prompt: LLM knowledge + release notes
        messages = [
            {
                "role": "system",
                "content": f"""Analyze Java code for JDK {from_version} to {to_version} upgrade issues.
Use your knowledge of JDK changes plus any release notes provided.
Return ONLY a JSON array. No explanation. Example format:
[{{"line":59,"code":"setEnabledProtocols","issue":"TLS 1.0/1.1 disabled in 11.0.19+","severity":"high","category":"security"}}]
Return [] if no issues.""",
            },
            {
                "role": "user",
                "content": f"""Release notes: {release_context[:500] if release_context else "Use JDK knowledge."}

{file_path.name}:
{content}

JSON:""",
            },
        ]

        try:
            response = await self.llm.complete(messages, llm_provider, temperature=0.1, max_tokens=2048)
            logger.debug(f"[Analyzer] LLM response: {response[:500]}...")

            # Parse response - handle various formats
            response = response.strip()

            # Remove markdown code blocks
            response = re.sub(r"```(?:json)?\s*", "", response)
            response = re.sub(r"```\s*$", "", response)
            response = response.strip()

            # Try to find JSON array in response
            array_match = re.search(r'\[[\s\S]*\]', response)
            if array_match:
                response = array_match.group(0)

            # Fix common JSON issues from LLMs
            # Replace newlines inside strings with escaped newlines
            # This is a simple heuristic - find strings and escape newlines in them
            def fix_json_strings(text):
                # Replace literal newlines with \n in JSON strings
                result = []
                in_string = False
                escape_next = False
                for char in text:
                    if escape_next:
                        result.append(char)
                        escape_next = False
                    elif char == '\\':
                        result.append(char)
                        escape_next = True
                    elif char == '"':
                        result.append(char)
                        in_string = not in_string
                    elif char == '\n' and in_string:
                        result.append('\\n')
                    else:
                        result.append(char)
                return ''.join(result)

            response = fix_json_strings(response)

            try:
                issues = json.loads(response)
            except json.JSONDecodeError:
                # Try to extract individual issue objects
                logger.warning(f"[Analyzer] JSON parse failed, trying fallback extraction")
                issues = []
                # Find all {...} objects
                for obj_match in re.finditer(r'\{[^{}]+\}', response):
                    try:
                        obj_text = fix_json_strings(obj_match.group(0))
                        obj = json.loads(obj_text)
                        if "line" in obj or "issue" in obj:
                            issues.append(obj)
                    except:
                        pass
                if not issues:
                    logger.warning(f"[Analyzer] Could not parse any issues from response")
                    return []

            # Convert to ImpactItems
            impacts = []
            for issue in issues:
                if not isinstance(issue, dict):
                    continue

                severity_map = {
                    "high": RiskLevel.HIGH,
                    "critical": RiskLevel.CRITICAL,
                    "medium": RiskLevel.MEDIUM,
                    "low": RiskLevel.LOW,
                }
                category_map = {
                    "security": ChangeType.SECURITY,
                    "deprecated": ChangeType.DEPRECATED,
                    "behavioral": ChangeType.BEHAVIORAL,
                    "removed": ChangeType.REMOVED,
                }

                impacts.append(ImpactItem(
                    location=CodeLocation(
                        file_path=str(file_path),
                        line_number=issue.get("line", 0),
                        column_number=0,
                        code_snippet=issue.get("code", "")[:150],
                    ),
                    change=JDKChange(
                        version=to_version,
                        change_type=category_map.get(issue.get("category", ""), ChangeType.BEHAVIORAL),
                        component="",
                        description=issue.get("issue", ""),
                        affected_classes=[],
                        affected_methods=[],
                    ),
                    severity=severity_map.get(issue.get("severity", "medium"), RiskLevel.MEDIUM),
                    affected_class=None,
                    affected_method=None,
                ))

            return impacts

        except Exception as e:
            logger.warning(f"[Analyzer] LLM analysis failed for {file_path.name}: {e}")
            # Fallback to basic analysis
            return await self._analyze_file_basic(file_path, release_notes_changes)

    async def _analyze_file_basic(
        self,
        file_path: Path,
        changes: list[JDKChange],
    ) -> list[ImpactItem]:
        """Basic AST-based analysis without LLM (fallback)."""
        impacts: list[ImpactItem] = []

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            return impacts

        # Parse the file with tree-sitter
        parser = self._get_parser()
        tree = parser.parse(content.encode())

        # Extract actual code usages only
        usages = self._extract_usages(tree, content)

        # Match against changes from release notes
        for change in changes:
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

        # Deduplicate
        seen = set()
        unique_impacts = []
        for impact in impacts:
            key = (impact.location.file_path, impact.location.line_number)
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
        """Extract class and method usages from AST - focus on actual code, not declarations."""
        usages = []

        def get_parent_type(node):
            """Get the parent node type to understand context."""
            parent = node.parent
            while parent:
                if parent.type in ("method_declaration", "formal_parameter", "field_declaration",
                                   "local_variable_declaration", "import_declaration"):
                    return parent.type
                parent = parent.parent
            return None

        def visit(node):
            # Method invocations - these are actual code usage
            if node.type == "method_invocation":
                method_name = None
                class_name = None

                for child in node.children:
                    if child.type == "identifier":
                        method_name = content[child.start_byte : child.end_byte]
                    elif child.type == "field_access":
                        class_name = content[child.start_byte : child.end_byte]
                    elif child.type == "identifier" and class_name is None:
                        # Could be the object/class being called on
                        pass

                if method_name:
                    usages.append({
                        "name": f"{class_name}.{method_name}" if class_name else method_name,
                        "line": node.start_point[0] + 1,
                        "column": node.start_point[1],
                        "code": content[node.start_byte : node.end_byte][:100],
                        "class": class_name,
                        "method": method_name,
                        "context": "method_call",
                    })

            # Object creation expressions - actual instantiation
            elif node.type == "object_creation_expression":
                for child in node.children:
                    if child.type == "type_identifier":
                        type_name = content[child.start_byte : child.end_byte]
                        usages.append({
                            "name": type_name,
                            "line": node.start_point[0] + 1,
                            "column": node.start_point[1],
                            "code": content[node.start_byte : node.end_byte][:100],
                            "class": type_name,
                            "method": "new",
                            "context": "instantiation",
                        })

            # Skip type_identifier in declarations - they're not the actual problem
            # We only care about instantiations and method calls

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
