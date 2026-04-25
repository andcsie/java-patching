"""Service for Renovate-style dependency and JDK version management."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx
from lxml import etree

from app.core.config import settings


@dataclass
class JDKVersion:
    """Parsed JDK version information."""

    major: int
    minor: int
    patch: int
    full: str
    source_file: str
    source_line: int | None = None

    @property
    def semver(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def __gt__(self, other: "JDKVersion") -> bool:
        return self.semver > other.semver

    def __lt__(self, other: "JDKVersion") -> bool:
        return self.semver < other.semver


@dataclass
class AvailablePatch:
    """Available JDK patch version."""

    version: str
    release_date: str
    release_type: str  # "ga", "ea"
    download_url: str | None
    release_notes_url: str | None
    security_fixes: list[str]
    is_lts: bool


@dataclass
class VersionBump:
    """A version bump to apply."""

    file_path: str
    old_version: str
    new_version: str
    line_number: int
    old_content: str
    new_content: str
    diff: str


class RenovateService:
    """Service for managing JDK versions and patches like Renovate."""

    ADOPTIUM_API = "https://api.adoptium.net/v3"
    MAVEN_CENTRAL = "https://search.maven.org/solrsearch/select"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    # =========================================================================
    # Version Detection
    # =========================================================================

    async def detect_jdk_version(self, repo_path: Path) -> JDKVersion | None:
        """Detect JDK version from build files in priority order."""
        detectors = [
            self._detect_from_pom_xml,
            self._detect_from_gradle,
            self._detect_from_gradle_kts,
            self._detect_from_java_version_file,
            self._detect_from_sdkmanrc,
            self._detect_from_tool_versions,
        ]

        for detector in detectors:
            version = await detector(repo_path)
            if version:
                return version

        return None

    async def _detect_from_pom_xml(self, repo_path: Path) -> JDKVersion | None:
        """Detect JDK version from Maven pom.xml."""
        pom_path = repo_path / "pom.xml"
        if not pom_path.exists():
            return None

        try:
            content = pom_path.read_text()
            tree = etree.fromstring(content.encode())

            # Remove namespace for easier querying
            for elem in tree.iter():
                if elem.tag.startswith("{"):
                    elem.tag = elem.tag.split("}", 1)[1]

            # Check various version properties
            patterns = [
                ".//properties/java.version",
                ".//properties/maven.compiler.source",
                ".//properties/maven.compiler.target",
                ".//properties/maven.compiler.release",
                ".//build/plugins/plugin[artifactId='maven-compiler-plugin']/configuration/source",
                ".//build/plugins/plugin[artifactId='maven-compiler-plugin']/configuration/release",
            ]

            for pattern in patterns:
                elem = tree.find(pattern)
                if elem is not None and elem.text:
                    version = self._parse_version_string(elem.text.strip())
                    if version:
                        # Find line number
                        line_num = self._find_line_number(content, elem.text)
                        return JDKVersion(
                            major=version[0],
                            minor=version[1],
                            patch=version[2],
                            full=elem.text.strip(),
                            source_file=str(pom_path),
                            source_line=line_num,
                        )
        except Exception:
            pass

        return None

    async def _detect_from_gradle(self, repo_path: Path) -> JDKVersion | None:
        """Detect JDK version from build.gradle."""
        gradle_path = repo_path / "build.gradle"
        if not gradle_path.exists():
            return None

        return await self._parse_gradle_file(gradle_path)

    async def _detect_from_gradle_kts(self, repo_path: Path) -> JDKVersion | None:
        """Detect JDK version from build.gradle.kts."""
        gradle_path = repo_path / "build.gradle.kts"
        if not gradle_path.exists():
            return None

        return await self._parse_gradle_file(gradle_path)

    async def _parse_gradle_file(self, gradle_path: Path) -> JDKVersion | None:
        """Parse Gradle file for JDK version."""
        try:
            content = gradle_path.read_text()

            patterns = [
                (r"sourceCompatibility\s*=\s*['\"]?(\d+(?:\.\d+)*)['\"]?", 1),
                (r"targetCompatibility\s*=\s*['\"]?(\d+(?:\.\d+)*)['\"]?", 1),
                (r"JavaVersion\.VERSION_(\d+)", 1),
                (r"languageVersion\.set\(JavaLanguageVersion\.of\((\d+)\)\)", 1),
                (r"jvmTarget\s*=\s*['\"](\d+(?:\.\d+)*)['\"]", 1),
            ]

            for pattern, group in patterns:
                match = re.search(pattern, content)
                if match:
                    version_str = match.group(group)
                    version = self._parse_version_string(version_str)
                    if version:
                        line_num = content[:match.start()].count("\n") + 1
                        return JDKVersion(
                            major=version[0],
                            minor=version[1],
                            patch=version[2],
                            full=version_str,
                            source_file=str(gradle_path),
                            source_line=line_num,
                        )
        except Exception:
            pass

        return None

    async def _detect_from_java_version_file(self, repo_path: Path) -> JDKVersion | None:
        """Detect from .java-version file."""
        java_version_path = repo_path / ".java-version"
        if not java_version_path.exists():
            return None

        try:
            content = java_version_path.read_text().strip()
            version = self._parse_version_string(content)
            if version:
                return JDKVersion(
                    major=version[0],
                    minor=version[1],
                    patch=version[2],
                    full=content,
                    source_file=str(java_version_path),
                    source_line=1,
                )
        except Exception:
            pass

        return None

    async def _detect_from_sdkmanrc(self, repo_path: Path) -> JDKVersion | None:
        """Detect from .sdkmanrc file."""
        sdkmanrc_path = repo_path / ".sdkmanrc"
        if not sdkmanrc_path.exists():
            return None

        try:
            content = sdkmanrc_path.read_text()
            match = re.search(r"java\s*=\s*(\S+)", content)
            if match:
                version_str = match.group(1)
                # SDKMAN format: 11.0.22-tem, 17.0.10-zulu, etc.
                version_match = re.match(r"(\d+)\.(\d+)\.(\d+)", version_str)
                if version_match:
                    return JDKVersion(
                        major=int(version_match.group(1)),
                        minor=int(version_match.group(2)),
                        patch=int(version_match.group(3)),
                        full=version_str,
                        source_file=str(sdkmanrc_path),
                        source_line=content[:match.start()].count("\n") + 1,
                    )
        except Exception:
            pass

        return None

    async def _detect_from_tool_versions(self, repo_path: Path) -> JDKVersion | None:
        """Detect from .tool-versions (asdf) file."""
        tool_versions_path = repo_path / ".tool-versions"
        if not tool_versions_path.exists():
            return None

        try:
            content = tool_versions_path.read_text()
            match = re.search(r"java\s+(\S+)", content)
            if match:
                version_str = match.group(1)
                # asdf format varies: temurin-11.0.22, adoptopenjdk-11.0.22, etc.
                version_match = re.search(r"(\d+)\.(\d+)\.(\d+)", version_str)
                if version_match:
                    return JDKVersion(
                        major=int(version_match.group(1)),
                        minor=int(version_match.group(2)),
                        patch=int(version_match.group(3)),
                        full=version_str,
                        source_file=str(tool_versions_path),
                        source_line=content[:match.start()].count("\n") + 1,
                    )
        except Exception:
            pass

        return None

    def _parse_version_string(self, version_str: str) -> tuple[int, int, int] | None:
        """Parse a version string into (major, minor, patch)."""
        # Handle formats: "11", "11.0", "11.0.22", "1.8", "1.8.0_352"
        version_str = version_str.strip()

        # Java 8 style: 1.8.0_352
        if version_str.startswith("1."):
            match = re.match(r"1\.(\d+)(?:\.(\d+))?(?:_(\d+))?", version_str)
            if match:
                return (
                    int(match.group(1)),
                    int(match.group(2) or 0),
                    int(match.group(3) or 0),
                )

        # Modern style: 11.0.22
        match = re.match(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", version_str)
        if match:
            return (
                int(match.group(1)),
                int(match.group(2) or 0),
                int(match.group(3) or 0),
            )

        return None

    def _find_line_number(self, content: str, search_text: str) -> int | None:
        """Find line number of text in content."""
        idx = content.find(search_text)
        if idx == -1:
            return None
        return content[:idx].count("\n") + 1

    # =========================================================================
    # Patch Discovery
    # =========================================================================

    async def get_available_patches(
        self,
        current_version: JDKVersion,
        include_ea: bool = False,
    ) -> list[AvailablePatch]:
        """Get available patch versions for the current JDK major version."""
        patches = []

        try:
            # Fetch releases from Adoptium API
            url = f"{self.ADOPTIUM_API}/info/release_versions"
            params = {
                "architecture": "x64",
                "heap_size": "normal",
                "image_type": "jdk",
                "os": "linux",
                "page": 0,
                "page_size": 50,
                "project": "jdk",
                "release_type": "ga",
                "sort_method": "DATE",
                "sort_order": "DESC",
                "vendor": "eclipse",
                "version": f"[{current_version.major},{current_version.major + 1})",
            }

            response = await self.client.get(url, params=params)
            if response.status_code != 200:
                return patches

            data = response.json()

            for version_info in data.get("versions", []):
                semver = version_info.get("semver", "")
                version_tuple = self._parse_version_string(semver)

                if not version_tuple:
                    continue

                # Only include patches newer than current
                if version_tuple <= current_version.semver:
                    continue

                # Fetch additional release info
                release_info = await self._get_release_info(semver)

                patches.append(
                    AvailablePatch(
                        version=semver,
                        release_date=version_info.get("release_date", ""),
                        release_type="ga",
                        download_url=release_info.get("download_url"),
                        release_notes_url=release_info.get("release_notes_url"),
                        security_fixes=release_info.get("security_fixes", []),
                        is_lts=current_version.major in [8, 11, 17, 21],
                    )
                )

        except Exception:
            pass

        return sorted(patches, key=lambda p: self._parse_version_string(p.version) or (0, 0, 0))

    async def _get_release_info(self, version: str) -> dict:
        """Get detailed release information."""
        info = {
            "download_url": None,
            "release_notes_url": None,
            "security_fixes": [],
        }

        try:
            # Get release notes URL
            major = version.split(".")[0]
            info["release_notes_url"] = (
                f"https://www.oracle.com/java/technologies/javase/{major}u-relnotes.html"
            )

            # Try to get binary info
            url = f"{self.ADOPTIUM_API}/assets/latest/{major}/hotspot"
            response = await self.client.get(url, params={"os": "linux", "architecture": "x64"})
            if response.status_code == 200:
                data = response.json()
                if data:
                    info["download_url"] = data[0].get("binary", {}).get("package", {}).get("link")

        except Exception:
            pass

        return info

    # =========================================================================
    # Version Bumping
    # =========================================================================

    async def generate_version_bump(
        self,
        repo_path: Path,
        target_version: str,
    ) -> list[VersionBump]:
        """Generate version bumps for all build files."""
        bumps = []
        current = await self.detect_jdk_version(repo_path)

        if not current:
            return bumps

        target_tuple = self._parse_version_string(target_version)
        if not target_tuple:
            return bumps

        # Only allow same-major patches
        if target_tuple[0] != current.major:
            return bumps

        # Generate bumps for each file type
        bump_generators = [
            self._generate_pom_bump,
            self._generate_gradle_bump,
            self._generate_java_version_bump,
            self._generate_sdkmanrc_bump,
            self._generate_tool_versions_bump,
        ]

        for generator in bump_generators:
            bump = await generator(repo_path, current.full, target_version)
            if bump:
                bumps.append(bump)

        return bumps

    async def _generate_pom_bump(
        self,
        repo_path: Path,
        old_version: str,
        new_version: str,
    ) -> VersionBump | None:
        """Generate version bump for pom.xml."""
        pom_path = repo_path / "pom.xml"
        if not pom_path.exists():
            return None

        content = pom_path.read_text()

        # Find and replace java.version property
        patterns = [
            (r"(<java\.version>)[^<]+(</java\.version>)", rf"\g<1>{new_version}\g<2>"),
            (r"(<maven\.compiler\.source>)[^<]+(</maven\.compiler\.source>)", rf"\g<1>{new_version}\g<2>"),
            (r"(<maven\.compiler\.target>)[^<]+(</maven\.compiler\.target>)", rf"\g<1>{new_version}\g<2>"),
        ]

        new_content = content
        for pattern, replacement in patterns:
            new_content = re.sub(pattern, replacement, new_content)

        if new_content == content:
            return None

        # Find line number of first change
        line_num = 1
        for i, (old_line, new_line) in enumerate(zip(content.split("\n"), new_content.split("\n"))):
            if old_line != new_line:
                line_num = i + 1
                break

        return VersionBump(
            file_path=str(pom_path),
            old_version=old_version,
            new_version=new_version,
            line_number=line_num,
            old_content=content,
            new_content=new_content,
            diff=self._generate_diff(content, new_content, "pom.xml"),
        )

    async def _generate_gradle_bump(
        self,
        repo_path: Path,
        old_version: str,
        new_version: str,
    ) -> VersionBump | None:
        """Generate version bump for build.gradle or build.gradle.kts."""
        for filename in ["build.gradle", "build.gradle.kts"]:
            gradle_path = repo_path / filename
            if not gradle_path.exists():
                continue

            content = gradle_path.read_text()

            # Various Gradle version patterns
            patterns = [
                (rf"(sourceCompatibility\s*=\s*['\"]?){re.escape(old_version)}(['\"]?)", rf"\g<1>{new_version}\g<2>"),
                (rf"(targetCompatibility\s*=\s*['\"]?){re.escape(old_version)}(['\"]?)", rf"\g<1>{new_version}\g<2>"),
            ]

            new_content = content
            for pattern, replacement in patterns:
                new_content = re.sub(pattern, replacement, new_content)

            if new_content != content:
                line_num = 1
                for i, (old_line, new_line) in enumerate(zip(content.split("\n"), new_content.split("\n"))):
                    if old_line != new_line:
                        line_num = i + 1
                        break

                return VersionBump(
                    file_path=str(gradle_path),
                    old_version=old_version,
                    new_version=new_version,
                    line_number=line_num,
                    old_content=content,
                    new_content=new_content,
                    diff=self._generate_diff(content, new_content, filename),
                )

        return None

    async def _generate_java_version_bump(
        self,
        repo_path: Path,
        old_version: str,
        new_version: str,
    ) -> VersionBump | None:
        """Generate version bump for .java-version."""
        path = repo_path / ".java-version"
        if not path.exists():
            return None

        content = path.read_text()
        new_content = new_version + "\n"

        if content.strip() == new_version:
            return None

        return VersionBump(
            file_path=str(path),
            old_version=content.strip(),
            new_version=new_version,
            line_number=1,
            old_content=content,
            new_content=new_content,
            diff=self._generate_diff(content, new_content, ".java-version"),
        )

    async def _generate_sdkmanrc_bump(
        self,
        repo_path: Path,
        old_version: str,
        new_version: str,
    ) -> VersionBump | None:
        """Generate version bump for .sdkmanrc."""
        path = repo_path / ".sdkmanrc"
        if not path.exists():
            return None

        content = path.read_text()
        # Preserve the vendor suffix if present
        match = re.search(r"java\s*=\s*\d+\.\d+\.\d+(-\w+)?", content)
        if not match:
            return None

        vendor_suffix = match.group(1) or "-tem"
        new_content = re.sub(
            r"(java\s*=\s*)\d+\.\d+\.\d+(-\w+)?",
            rf"\g<1>{new_version}{vendor_suffix}",
            content,
        )

        if new_content == content:
            return None

        return VersionBump(
            file_path=str(path),
            old_version=old_version,
            new_version=new_version,
            line_number=1,
            old_content=content,
            new_content=new_content,
            diff=self._generate_diff(content, new_content, ".sdkmanrc"),
        )

    async def _generate_tool_versions_bump(
        self,
        repo_path: Path,
        old_version: str,
        new_version: str,
    ) -> VersionBump | None:
        """Generate version bump for .tool-versions."""
        path = repo_path / ".tool-versions"
        if not path.exists():
            return None

        content = path.read_text()
        # Preserve the distribution prefix if present
        match = re.search(r"java\s+(\w+-)?(\d+\.\d+\.\d+)", content)
        if not match:
            return None

        prefix = match.group(1) or "temurin-"
        new_content = re.sub(
            r"(java\s+)(\w+-)?(\d+\.\d+\.\d+)",
            rf"\g<1>{prefix}{new_version}",
            content,
        )

        if new_content == content:
            return None

        return VersionBump(
            file_path=str(path),
            old_version=old_version,
            new_version=new_version,
            line_number=1,
            old_content=content,
            new_content=new_content,
            diff=self._generate_diff(content, new_content, ".tool-versions"),
        )

    def _generate_diff(self, old_content: str, new_content: str, filename: str) -> str:
        """Generate a unified diff between old and new content."""
        import difflib

        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
        )

        return "".join(diff)

    async def apply_version_bump(self, bump: VersionBump) -> bool:
        """Apply a version bump to the file."""
        try:
            path = Path(bump.file_path)
            path.write_text(bump.new_content)
            return True
        except Exception:
            return False

    # =========================================================================
    # Renovate Config Generation
    # =========================================================================

    async def generate_renovate_config(
        self,
        repo_path: Path,
        target_jdk: str | None = None,
    ) -> dict:
        """Generate a renovate.json configuration."""
        current = await self.detect_jdk_version(repo_path)

        config = {
            "$schema": "https://docs.renovatebot.com/renovate-schema.json",
            "extends": [
                "config:base",
                ":semanticCommits",
            ],
            "java": {
                "enabled": True,
            },
            "packageRules": [
                {
                    "matchManagers": ["maven", "gradle"],
                    "matchUpdateTypes": ["patch"],
                    "groupName": "JDK patch updates",
                    "automerge": False,
                    "labels": ["dependencies", "java", "patch"],
                },
                {
                    "matchManagers": ["maven", "gradle"],
                    "matchUpdateTypes": ["minor"],
                    "groupName": "JDK minor updates",
                    "automerge": False,
                    "labels": ["dependencies", "java", "minor"],
                },
            ],
            "vulnerabilityAlerts": {
                "enabled": True,
                "labels": ["security"],
            },
        }

        # Add version constraint if specified
        if target_jdk:
            config["packageRules"].insert(
                0,
                {
                    "matchManagers": ["maven", "gradle"],
                    "matchPackageNames": ["java"],
                    "allowedVersions": f"<={target_jdk}",
                },
            )

        return config

    async def save_renovate_config(self, repo_path: Path, config: dict) -> str:
        """Save renovate.json to repository."""
        config_path = repo_path / "renovate.json"
        config_path.write_text(json.dumps(config, indent=2))
        return str(config_path)


# Global instance
renovate_service = RenovateService()
