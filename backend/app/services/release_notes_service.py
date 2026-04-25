"""Service for fetching and parsing JDK release notes."""

import logging
import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.models.analysis import ChangeType


@dataclass
class JDKChange:
    """Represents a single JDK change."""

    version: str
    change_type: ChangeType
    component: str
    description: str
    affected_classes: list[str]
    affected_methods: list[str]
    cve_id: str | None = None
    migration_notes: str | None = None
    bug_id: str | None = None
    release_note_url: str | None = None


class ReleaseNotesService:
    """Service for fetching JDK release notes from various sources."""

    def __init__(self):
        # Short timeout - fail fast if APIs are slow
        self.client = httpx.AsyncClient(timeout=3.0)
        self._change_cache: dict[str, list[JDKChange]] = {}

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def get_changes_between_versions(
        self,
        from_version: str,
        to_version: str,
    ) -> list[JDKChange]:
        """Get all changes between two JDK versions."""
        import asyncio

        logging.info(f"[ReleaseNotes] Getting changes: {from_version} -> {to_version}")

        # Parse version numbers
        from_parts = self._parse_version(from_version)
        to_parts = self._parse_version(to_version)

        if from_parts is None or to_parts is None:
            logging.warning(f"[ReleaseNotes] Invalid version format")
            return []

        # Only support same major version upgrades for patch analysis
        if from_parts[0] != to_parts[0]:
            logging.warning(f"[ReleaseNotes] Cross-major upgrades not supported")
            return []

        major_version = from_parts[0]
        from_patch = from_parts[2] if len(from_parts) > 2 else from_parts[1]
        to_patch = to_parts[2] if len(to_parts) > 2 else to_parts[1]

        # Build list of versions to fetch
        versions_to_fetch = [
            f"{major_version}.0.{patch}"
            for patch in range(from_patch + 1, to_patch + 1)
        ]

        if not versions_to_fetch:
            return []

        logging.info(f"[ReleaseNotes] Fetching {len(versions_to_fetch)} versions in parallel")

        # Fetch all versions in parallel
        tasks = [self._get_version_changes(v) for v in versions_to_fetch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_changes: list[JDKChange] = []
        for version_str, result in zip(versions_to_fetch, results):
            if isinstance(result, Exception):
                logging.warning(f"[ReleaseNotes] Failed to fetch {version_str}: {result}")
            else:
                logging.info(f"[ReleaseNotes] Got {len(result)} changes for {version_str}")
                all_changes.extend(result)

        logging.info(f"[ReleaseNotes] Total changes found: {len(all_changes)}")
        return all_changes

    def _parse_version(self, version: str) -> tuple[int, int, int] | None:
        """Parse a version string like '11.0.18' into (11, 0, 18)."""
        match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
        if not match:
            return None
        return int(match.group(1)), int(match.group(2)), int(match.group(3))

    async def _get_version_changes(self, version: str) -> list[JDKChange]:
        """Get changes for a specific JDK version."""
        import asyncio

        if version in self._change_cache:
            return self._change_cache[version]

        # Fetch from Oracle and Adoptium in parallel
        openjdk_task = self._fetch_openjdk_changes(version)
        adoptium_task = self._fetch_adoptium_changes(version)

        results = await asyncio.gather(openjdk_task, adoptium_task, return_exceptions=True)

        changes: list[JDKChange] = []
        for result in results:
            if isinstance(result, Exception):
                logging.warning(f"[ReleaseNotes] Fetch error for {version}: {result}")
            else:
                changes.extend(result)

        # Cache the results
        self._change_cache[version] = changes
        return changes

    async def _fetch_openjdk_changes(self, version: str) -> list[JDKChange]:
        """Fetch changes from Oracle JDK release notes."""
        changes: list[JDKChange] = []

        # Oracle release notes URL pattern (e.g., 11-0-22-relnotes.html)
        version_dashed = version.replace(".", "-")
        url = f"https://www.oracle.com/java/technologies/javase/{version_dashed}-relnotes.html"

        logging.info(f"[ReleaseNotes] Fetching Oracle: {url}")
        try:
            response = await self.client.get(url, follow_redirects=True)
            logging.info(f"[ReleaseNotes] Oracle response: {response.status_code}")
            if response.status_code != 200:
                return changes

            soup = BeautifulSoup(response.text, "html.parser")

            # Parse security-libs changes
            for div in soup.find_all("div"):
                text = div.get_text()
                if "security-libs" in text.lower():
                    # Find the parent section for context
                    parent = div.find_parent("div") or div.find_parent("td")
                    if parent:
                        full_text = parent.get_text()
                        component = self._extract_component(full_text)
                        affected_classes = self._extract_class_names(full_text)

                        # Look for JDK bug link
                        bug_link = parent.find("a", href=re.compile(r"JDK-\d+"))
                        bug_id = None
                        if bug_link:
                            match = re.search(r"JDK-\d+", bug_link.get("href", ""))
                            if match:
                                bug_id = match.group()

                        changes.append(
                            JDKChange(
                                version=version,
                                change_type=ChangeType.SECURITY,
                                component=component,
                                description=full_text[:500].strip(),
                                affected_classes=affected_classes,
                                affected_methods=[],
                                bug_id=bug_id,
                            )
                        )

            # Parse Bug Fixes section
            bugfix_headers = soup.find_all(string=re.compile(r"Bug\s*Fix", re.I))
            for header in bugfix_headers:
                table = header.find_next("table")
                if table:
                    for row in table.find_all("tr")[1:]:  # Skip header row
                        cells = row.find_all("td")
                        if len(cells) >= 2:
                            bug_link = cells[0].find("a")
                            bug_id = bug_link.get_text().strip() if bug_link else None
                            description = cells[1].get_text().strip() if len(cells) > 1 else ""

                            component = self._extract_component(description)
                            affected_classes = self._extract_class_names(description)

                            # Determine change type
                            change_type = ChangeType.BUGFIX
                            if any(kw in description.lower() for kw in ["behavior", "change", "now"]):
                                change_type = ChangeType.BEHAVIORAL

                            changes.append(
                                JDKChange(
                                    version=version,
                                    change_type=change_type,
                                    component=component,
                                    description=description,
                                    affected_classes=affected_classes,
                                    affected_methods=[],
                                    bug_id=bug_id,
                                )
                            )

            # Parse CVE references
            cve_pattern = re.compile(r"CVE-\d{4}-\d+")
            for match in cve_pattern.finditer(soup.get_text()):
                cve_id = match.group()
                # Get context around CVE
                text = soup.get_text()
                start = max(0, match.start() - 200)
                end = min(len(text), match.end() + 200)
                context = text[start:end].strip()

                # Avoid duplicate CVEs
                if not any(c.cve_id == cve_id for c in changes):
                    changes.append(
                        JDKChange(
                            version=version,
                            change_type=ChangeType.SECURITY,
                            component=self._extract_component(context),
                            description=context,
                            affected_classes=self._extract_class_names(context),
                            affected_methods=[],
                            cve_id=cve_id,
                        )
                    )

        except Exception as e:
            logging.warning(f"Failed to fetch Oracle release notes for {version}: {e}")

        return changes

    async def _fetch_adoptium_changes(self, version: str) -> list[JDKChange]:
        """Fetch release info from Adoptium API."""
        changes: list[JDKChange] = []
        major = version.split(".")[0]

        # Get release info for the specific version
        url = f"{settings.adoptium_api_url}/assets/version/{version}"

        try:
            response = await self.client.get(url, params={"release_type": "ga"})
            if response.status_code != 200:
                return changes

            data = response.json()

            # Adoptium provides binary info, not detailed release notes
            # But we can extract version metadata
            for release in data if isinstance(data, list) else [data]:
                release_name = release.get("release_name", "")
                if release_name:
                    changes.append(
                        JDKChange(
                            version=version,
                            change_type=ChangeType.BUGFIX,
                            component="core",
                            description=f"Release: {release_name}",
                            affected_classes=[],
                            affected_methods=[],
                            release_note_url=f"https://adoptium.net/temurin/release-notes/?version=jdk-{version}",
                        )
                    )

        except Exception:
            pass

        return changes

    def _extract_component(self, text: str) -> str:
        """Extract JDK component from text."""
        # Common JDK component patterns
        component_patterns = [
            r"(java\.security)",
            r"(java\.lang)",
            r"(java\.util)",
            r"(java\.io)",
            r"(java\.net)",
            r"(java\.nio)",
            r"(javax\.crypto)",
            r"(javax\.net\.ssl)",
            r"(jdk\.security)",
            r"(sun\.security)",
            r"(hotspot)",
            r"(gc|garbage\s*collect)",
            r"(jit|compiler)",
        ]

        text_lower = text.lower()
        for pattern in component_patterns:
            match = re.search(pattern, text_lower)
            if match:
                return match.group(1)

        return "core"

    def _extract_class_names(self, text: str) -> list[str]:
        """Extract Java class names from text."""
        # Pattern for fully qualified class names
        pattern = re.compile(r"\b((?:java|javax|jdk|sun)\.[a-zA-Z0-9_.]+[A-Z][a-zA-Z0-9]*)\b")
        matches = pattern.findall(text)
        return list(set(matches))


# Global instance
release_notes_service = ReleaseNotesService()
