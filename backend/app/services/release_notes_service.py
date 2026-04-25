"""Service for fetching and parsing JDK release notes."""

import re
from dataclasses import dataclass
from functools import lru_cache

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
        self.client = httpx.AsyncClient(timeout=30.0)
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
        # Parse version numbers
        from_parts = self._parse_version(from_version)
        to_parts = self._parse_version(to_version)

        if from_parts is None or to_parts is None:
            return []

        # Only support same major version upgrades
        if from_parts[0] != to_parts[0]:
            return []

        major_version = from_parts[0]
        all_changes: list[JDKChange] = []

        # Get changes for each minor version in between
        current_minor = from_parts[1]
        target_minor = to_parts[1]

        while current_minor < target_minor:
            next_minor = current_minor + 1
            version_str = f"{major_version}.0.{next_minor}"

            changes = await self._get_version_changes(version_str)
            all_changes.extend(changes)
            current_minor = next_minor

        return all_changes

    def _parse_version(self, version: str) -> tuple[int, int, int] | None:
        """Parse a version string like '11.0.18' into (11, 0, 18)."""
        match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
        if not match:
            return None
        return int(match.group(1)), int(match.group(2)), int(match.group(3))

    async def _get_version_changes(self, version: str) -> list[JDKChange]:
        """Get changes for a specific JDK version."""
        if version in self._change_cache:
            return self._change_cache[version]

        changes: list[JDKChange] = []

        # Try OpenJDK release notes
        openjdk_changes = await self._fetch_openjdk_changes(version)
        changes.extend(openjdk_changes)

        # Try Adoptium API
        adoptium_changes = await self._fetch_adoptium_changes(version)
        changes.extend(adoptium_changes)

        # Cache the results
        self._change_cache[version] = changes
        return changes

    async def _fetch_openjdk_changes(self, version: str) -> list[JDKChange]:
        """Fetch changes from OpenJDK release notes."""
        changes: list[JDKChange] = []
        major = version.split(".")[0]

        # OpenJDK release notes URL pattern
        url = f"https://openjdk.org/projects/jdk-updates/{major}u/jdk-{version}-release-notes"

        try:
            response = await self.client.get(url, follow_redirects=True)
            if response.status_code != 200:
                return changes

            soup = BeautifulSoup(response.text, "lxml")

            # Parse security fixes
            security_section = soup.find(string=re.compile("Security", re.I))
            if security_section:
                parent = security_section.find_parent()
                if parent:
                    security_changes = self._parse_security_section(parent, version)
                    changes.extend(security_changes)

            # Parse bug fixes
            bugfix_section = soup.find(string=re.compile("Bug Fixes", re.I))
            if bugfix_section:
                parent = bugfix_section.find_parent()
                if parent:
                    bugfix_changes = self._parse_bugfix_section(parent, version)
                    changes.extend(bugfix_changes)

            # Parse deprecated/removed APIs
            api_section = soup.find(string=re.compile("Deprecated|Removed", re.I))
            if api_section:
                parent = api_section.find_parent()
                if parent:
                    api_changes = self._parse_api_changes(parent, version)
                    changes.extend(api_changes)

        except Exception:
            # Log error but continue
            pass

        return changes

    async def _fetch_adoptium_changes(self, version: str) -> list[JDKChange]:
        """Fetch changes from Adoptium API."""
        changes: list[JDKChange] = []
        major = version.split(".")[0]

        url = f"{settings.adoptium_api_url}/info/release_notes/openjdk{major}"

        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                return changes

            data = response.json()

            # Parse release notes from Adoptium format
            for note in data.get("release_notes", []):
                if note.get("version_data", {}).get("semver") == version:
                    for item in note.get("release_items", []):
                        change = self._parse_adoptium_item(item, version)
                        if change:
                            changes.append(change)

        except Exception:
            pass

        return changes

    def _parse_security_section(
        self,
        section,
        version: str,
    ) -> list[JDKChange]:
        """Parse security fixes from HTML section."""
        changes: list[JDKChange] = []

        # Find all list items or paragraphs with CVE references
        cve_pattern = re.compile(r"CVE-\d{4}-\d+")
        text = section.get_text()

        for match in cve_pattern.finditer(text):
            cve_id = match.group()

            # Try to extract the surrounding description
            start = max(0, match.start() - 200)
            end = min(len(text), match.end() + 200)
            context = text[start:end].strip()

            # Extract affected component
            component = self._extract_component(context)
            affected_classes = self._extract_class_names(context)

            changes.append(
                JDKChange(
                    version=version,
                    change_type=ChangeType.SECURITY,
                    component=component,
                    description=context,
                    affected_classes=affected_classes,
                    affected_methods=[],
                    cve_id=cve_id,
                )
            )

        return changes

    def _parse_bugfix_section(
        self,
        section,
        version: str,
    ) -> list[JDKChange]:
        """Parse bug fixes from HTML section."""
        changes: list[JDKChange] = []

        # Find bug IDs (JDK-XXXXXXX format)
        bug_pattern = re.compile(r"JDK-\d+")
        text = section.get_text()

        for match in bug_pattern.finditer(text):
            bug_id = match.group()

            # Extract description
            start = match.end()
            end = text.find("\n", start)
            if end == -1:
                end = min(len(text), start + 200)
            description = text[start:end].strip(": \t")

            component = self._extract_component(description)
            affected_classes = self._extract_class_names(description)

            # Determine if this is a behavioral change based on keywords
            change_type = ChangeType.BUGFIX
            if any(
                keyword in description.lower()
                for keyword in ["behavior", "behavioural", "changed", "now"]
            ):
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

        return changes

    def _parse_api_changes(
        self,
        section,
        version: str,
    ) -> list[JDKChange]:
        """Parse deprecated/removed API changes."""
        changes: list[JDKChange] = []
        text = section.get_text()

        # Look for class/method patterns
        class_pattern = re.compile(
            r"(java[x]?\.[a-zA-Z0-9_.]+(?:Class|Interface|[A-Z][a-zA-Z]+))"
        )
        method_pattern = re.compile(r"([a-zA-Z]+\.[a-zA-Z]+\([^)]*\))")

        for match in class_pattern.finditer(text):
            class_name = match.group(1)

            # Determine if deprecated or removed
            start = max(0, match.start() - 50)
            context = text[start : match.end() + 50].lower()

            if "removed" in context or "remove" in context:
                change_type = ChangeType.REMOVED
            else:
                change_type = ChangeType.DEPRECATED

            component = class_name.rsplit(".", 1)[0] if "." in class_name else "core"

            changes.append(
                JDKChange(
                    version=version,
                    change_type=change_type,
                    component=component,
                    description=text[start : match.end() + 100].strip(),
                    affected_classes=[class_name],
                    affected_methods=[],
                )
            )

        return changes

    def _parse_adoptium_item(self, item: dict, version: str) -> JDKChange | None:
        """Parse a single release item from Adoptium API."""
        title = item.get("title", "")
        description = item.get("description", "")
        link = item.get("link", "")

        if not title:
            return None

        # Determine change type
        change_type = ChangeType.BUGFIX
        title_lower = title.lower()
        if "security" in title_lower or "cve" in title_lower:
            change_type = ChangeType.SECURITY
        elif "deprecated" in title_lower:
            change_type = ChangeType.DEPRECATED
        elif "removed" in title_lower:
            change_type = ChangeType.REMOVED
        elif "behavior" in title_lower:
            change_type = ChangeType.BEHAVIORAL

        # Extract CVE if present
        cve_match = re.search(r"CVE-\d{4}-\d+", title + description)
        cve_id = cve_match.group() if cve_match else None

        # Extract component and classes
        component = self._extract_component(title + description)
        affected_classes = self._extract_class_names(title + description)

        return JDKChange(
            version=version,
            change_type=change_type,
            component=component,
            description=f"{title}\n{description}".strip(),
            affected_classes=affected_classes,
            affected_methods=[],
            cve_id=cve_id,
            release_note_url=link,
        )

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


# Well-known deprecated/removed APIs by JDK version for fallback
KNOWN_CHANGES: dict[str, list[JDKChange]] = {
    "11.0.19": [
        JDKChange(
            version="11.0.19",
            change_type=ChangeType.SECURITY,
            component="java.security",
            description="TLS 1.0 and 1.1 disabled by default",
            affected_classes=["javax.net.ssl.SSLSocket", "javax.net.ssl.SSLEngine"],
            affected_methods=["setEnabledProtocols"],
        ),
    ],
    "11.0.20": [
        JDKChange(
            version="11.0.20",
            change_type=ChangeType.SECURITY,
            component="java.security",
            description="Strengthened certificate path validation",
            affected_classes=["java.security.cert.PKIXValidator"],
            affected_methods=[],
        ),
    ],
    "17.0.6": [
        JDKChange(
            version="17.0.6",
            change_type=ChangeType.DEPRECATED,
            component="java.lang",
            description="SecurityManager deprecated for removal",
            affected_classes=["java.lang.SecurityManager"],
            affected_methods=["checkPermission", "checkRead", "checkWrite"],
            migration_notes="Migrate to alternative security mechanisms",
        ),
    ],
    "21.0.1": [
        JDKChange(
            version="21.0.1",
            change_type=ChangeType.BEHAVIORAL,
            component="java.lang",
            description="Virtual threads now handle thread-local variables differently",
            affected_classes=["java.lang.ThreadLocal"],
            affected_methods=["get", "set", "remove"],
        ),
    ],
}


# Global instance
release_notes_service = ReleaseNotesService()
