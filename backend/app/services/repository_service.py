"""Service for managing repositories."""

import asyncio
import shutil
import uuid
from pathlib import Path

from git import Repo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.repository import Repository
from app.schemas.repository import RepositoryCreate, RepositoryUpdate


class RepositoryService:
    """Service for repository operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repos_base_path = Path(settings.repos_base_path)

    async def create(
        self,
        owner_id: uuid.UUID,
        repo_data: RepositoryCreate,
    ) -> Repository:
        """Create a new repository record."""
        # Auto-detect git provider from URL
        git_provider = self._detect_git_provider(repo_data.url)
        if hasattr(repo_data, 'git_provider') and repo_data.git_provider:
            git_provider = repo_data.git_provider.value if hasattr(repo_data.git_provider, 'value') else repo_data.git_provider

        auth_method = "ssh"
        if hasattr(repo_data, 'auth_method') and repo_data.auth_method:
            auth_method = repo_data.auth_method.value if hasattr(repo_data.auth_method, 'value') else repo_data.auth_method

        repo = Repository(
            name=repo_data.name,
            url=repo_data.url,
            description=repo_data.description,
            branch=repo_data.branch,
            current_jdk_version=repo_data.current_jdk_version,
            target_jdk_version=repo_data.target_jdk_version,
            owner_id=owner_id,
            git_provider=git_provider,
            auth_method=auth_method,
            access_token=getattr(repo_data, 'access_token', None),
        )
        self.db.add(repo)
        await self.db.commit()
        await self.db.refresh(repo)
        return repo

    def _detect_git_provider(self, url: str) -> str:
        """Auto-detect git provider from URL."""
        url_lower = url.lower()
        if "github.com" in url_lower or "github" in url_lower:
            return "github"
        elif "bitbucket.org" in url_lower or "bitbucket" in url_lower:
            return "bitbucket"
        elif "gitlab.com" in url_lower or "gitlab" in url_lower:
            return "gitlab"
        return "other"

    async def get_by_id(self, repo_id: uuid.UUID) -> Repository | None:
        """Get a repository by ID."""
        result = await self.db.execute(
            select(Repository).where(Repository.id == repo_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: uuid.UUID) -> list[Repository]:
        """Get all repositories for a user."""
        result = await self.db.execute(
            select(Repository)
            .where(Repository.owner_id == user_id)
            .where(Repository.is_active == True)
            .order_by(Repository.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(
        self,
        repo: Repository,
        repo_data: RepositoryUpdate,
    ) -> Repository:
        """Update a repository."""
        update_data = repo_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(repo, field, value)

        await self.db.commit()
        await self.db.refresh(repo)
        return repo

    async def delete(self, repo: Repository) -> None:
        """Soft delete a repository."""
        repo.is_active = False
        await self.db.commit()

        # Clean up local clone if exists
        if repo.local_path:
            await self._cleanup_local_clone(repo.local_path)

    async def clone(self, repo: Repository, use_ssh: bool | None = None) -> str:
        """Clone a repository to local storage.

        Args:
            repo: Repository to clone
            use_ssh: If True, use SSH. If False, use HTTPS. If None, auto-detect from auth_method.
        """
        import logging
        logger = logging.getLogger(__name__)

        # Check if URL is a local path (file:// or absolute path)
        if repo.url.startswith("file://"):
            local_path = repo.url[7:]  # Strip file://
            if Path(local_path).exists():
                repo.local_path = local_path
                await self.db.commit()
                return local_path
            else:
                raise ValueError(f"Local path does not exist: {local_path}")
        elif repo.url.startswith("/"):
            # Direct absolute path
            if Path(repo.url).exists():
                repo.local_path = repo.url
                await self.db.commit()
                return repo.url
            else:
                raise ValueError(f"Local path does not exist: {repo.url}")

        # Auto-detect auth method if not specified
        if use_ssh is None:
            use_ssh = getattr(repo, 'auth_method', 'ssh') == 'ssh'

        # Build clone URL based on auth method
        clone_url = repo.url
        if use_ssh:
            clone_url = self._convert_to_ssh_url(repo.url)
            logger.info(f"Using SSH URL: {clone_url}")
        elif getattr(repo, 'access_token', None):
            # Use PAT authentication
            clone_url = self._build_pat_url(repo.url, repo.access_token, getattr(repo, 'git_provider', 'github'))
            logger.info(f"Using PAT authentication for {repo.git_provider}")

        # Regular git clone
        local_path = self.repos_base_path / str(repo.owner_id) / str(repo.id)

        # Ensure parent directory exists
        local_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Cloning to {local_path}")

        # Clone in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                self._clone_sync,
                clone_url,
                local_path,
                repo.branch,
            )
        except Exception as e:
            logger.error(f"Clone failed: {e}")
            # If SSH failed, try PAT if available
            if use_ssh and getattr(repo, 'access_token', None):
                logger.info(f"SSH clone failed, trying PAT authentication")
                pat_url = self._build_pat_url(repo.url, repo.access_token, getattr(repo, 'git_provider', 'github'))
                await loop.run_in_executor(
                    None,
                    self._clone_sync,
                    pat_url,
                    local_path,
                    repo.branch,
                )
            # If PAT failed, try original URL
            elif clone_url != repo.url:
                logger.info(f"Trying original URL: {repo.url}")
                await loop.run_in_executor(
                    None,
                    self._clone_sync,
                    repo.url,
                    local_path,
                    repo.branch,
                )
            else:
                raise

        # Update repository with local path
        repo.local_path = str(local_path)
        await self.db.commit()

        return str(local_path)

    def _build_pat_url(self, url: str, token: str, provider: str = "github") -> str:
        """Build URL with PAT authentication embedded.

        Different providers have different formats:
        - GitHub: https://TOKEN@github.com/user/repo.git
        - Bitbucket: https://x-token-auth:TOKEN@bitbucket.org/user/repo.git
        - GitLab: https://oauth2:TOKEN@gitlab.com/user/repo.git
        """
        import re

        # Extract host and path from URL
        match = re.match(r'https?://([^/]+)/(.+?)(?:\.git)?$', url)
        if not match:
            return url

        host = match.group(1)
        path = match.group(2)

        if provider == "bitbucket":
            # Bitbucket uses x-token-auth format
            return f"https://x-token-auth:{token}@{host}/{path}.git"
        elif provider == "gitlab":
            # GitLab uses oauth2 format
            return f"https://oauth2:{token}@{host}/{path}.git"
        else:
            # GitHub and others use simple token format
            return f"https://{token}@{host}/{path}.git"

    def _convert_to_ssh_url(self, url: str) -> str:
        """Convert HTTPS URL to SSH URL format."""
        import re

        # Already SSH format
        if url.startswith("git@"):
            return url

        # GitHub HTTPS to SSH
        # https://github.com/user/repo.git -> git@github.com:user/repo.git
        match = re.match(r'https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?$', url)
        if match:
            return f"git@github.com:{match.group(1)}/{match.group(2)}.git"

        # Bitbucket HTTPS to SSH
        # https://bitbucket.org/user/repo.git -> git@bitbucket.org:user/repo.git
        match = re.match(r'https?://bitbucket\.org/([^/]+)/([^/]+?)(?:\.git)?$', url)
        if match:
            return f"git@bitbucket.org:{match.group(1)}/{match.group(2)}.git"

        # GitLab HTTPS to SSH
        # https://gitlab.com/user/repo.git -> git@gitlab.com:user/repo.git
        match = re.match(r'https?://gitlab\.com/([^/]+)/([^/]+?)(?:\.git)?$', url)
        if match:
            return f"git@gitlab.com:{match.group(1)}/{match.group(2)}.git"

        # Generic: try to convert any https://host/path to git@host:path
        match = re.match(r'https?://([^/]+)/(.+?)(?:\.git)?$', url)
        if match:
            return f"git@{match.group(1)}:{match.group(2)}.git"

        # Return original if can't convert
        return url

    def _clone_sync(self, url: str, local_path: Path, branch: str) -> None:
        """Synchronous clone operation."""
        if local_path.exists():
            shutil.rmtree(local_path)

        Repo.clone_from(
            url,
            local_path,
            branch=branch,
            depth=1,  # Shallow clone for efficiency
        )

    async def pull(self, repo: Repository) -> bool:
        """Pull latest changes for a repository."""
        if not repo.local_path:
            return False

        local_path = Path(repo.local_path)
        if not local_path.exists():
            return False

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._pull_sync,
            local_path,
        )

        return True

    def _pull_sync(self, local_path: Path) -> None:
        """Synchronous pull operation."""
        git_repo = Repo(local_path)
        git_repo.remotes.origin.pull()

    async def _cleanup_local_clone(self, local_path: str) -> None:
        """Clean up a local repository clone."""
        path = Path(local_path)
        if path.exists():
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, shutil.rmtree, path)

    async def get_java_files_count(self, repo: Repository) -> int:
        """Get count of Java files in repository."""
        if not repo.local_path:
            return 0

        local_path = Path(repo.local_path)
        if not local_path.exists():
            return 0

        loop = asyncio.get_event_loop()
        count = await loop.run_in_executor(
            None,
            lambda: len(list(local_path.rglob("*.java"))),
        )
        return count

    async def detect_jdk_version(self, repo: Repository) -> str | None:
        """Attempt to detect JDK version from build files."""
        if not repo.local_path:
            return None

        local_path = Path(repo.local_path)
        if not local_path.exists():
            return None

        # Check pom.xml for Maven projects
        pom_path = local_path / "pom.xml"
        if pom_path.exists():
            version = await self._detect_from_pom(pom_path)
            if version:
                return version

        # Check build.gradle for Gradle projects
        gradle_path = local_path / "build.gradle"
        if gradle_path.exists():
            version = await self._detect_from_gradle(gradle_path)
            if version:
                return version

        # Check build.gradle.kts for Kotlin DSL
        gradle_kts_path = local_path / "build.gradle.kts"
        if gradle_kts_path.exists():
            version = await self._detect_from_gradle(gradle_kts_path)
            if version:
                return version

        return None

    async def _detect_from_pom(self, pom_path: Path) -> str | None:
        """Detect JDK version from pom.xml."""
        import re

        try:
            content = pom_path.read_text()

            # Look for maven.compiler.source/target
            patterns = [
                r"<maven\.compiler\.source>(\d+(?:\.\d+)*)</maven\.compiler\.source>",
                r"<maven\.compiler\.target>(\d+(?:\.\d+)*)</maven\.compiler\.target>",
                r"<java\.version>(\d+(?:\.\d+)*)</java\.version>",
                r"<release>(\d+)</release>",
            ]

            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    version = match.group(1)
                    # Normalize version (e.g., "11" -> "11.0.0")
                    if "." not in version:
                        version = f"{version}.0.0"
                    return version

        except Exception:
            pass

        return None

    async def _detect_from_gradle(self, gradle_path: Path) -> str | None:
        """Detect JDK version from build.gradle."""
        import re

        try:
            content = gradle_path.read_text()

            # Look for sourceCompatibility/targetCompatibility
            patterns = [
                r"sourceCompatibility\s*=\s*['\"]?(\d+(?:\.\d+)*)['\"]?",
                r"targetCompatibility\s*=\s*['\"]?(\d+(?:\.\d+)*)['\"]?",
                r"JavaVersion\.VERSION_(\d+)",
                r"jvmTarget\s*=\s*['\"](\d+(?:\.\d+)*)['\"]",
            ]

            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    version = match.group(1)
                    # Handle JavaVersion.VERSION_X format
                    if version.isdigit() and int(version) < 20:
                        version = f"{version}.0.0"
                    elif "." not in version:
                        version = f"{version}.0.0"
                    return version

        except Exception:
            pass

        return None

    async def scan_and_discover(
        self,
        scan_path: Path,
        owner_id: uuid.UUID,
    ) -> list[Repository]:
        """Scan a directory for Java projects and import them."""
        discovered = []

        if not scan_path.exists():
            return discovered

        # Look for directories containing pom.xml or build.gradle
        for item in scan_path.iterdir():
            if not item.is_dir():
                continue

            # Skip hidden directories
            if item.name.startswith("."):
                continue

            # Check if it's a Java project
            is_maven = (item / "pom.xml").exists()
            is_gradle = (item / "build.gradle").exists() or (item / "build.gradle.kts").exists()

            if not (is_maven or is_gradle):
                continue

            # Check if already imported (by local_path or by name)
            result = await self.db.execute(
                select(Repository)
                .where(Repository.owner_id == owner_id)
                .where(
                    (Repository.local_path == str(item)) |
                    (Repository.name == item.name)
                )
                .where(Repository.is_active == True)
            )
            existing = result.scalar_one_or_none()
            if existing:
                # Update local_path if not set
                if not existing.local_path:
                    existing.local_path = str(item)
                    await self.db.commit()
                discovered.append(existing)
                continue

            # Create new repository record
            repo = Repository(
                name=item.name,
                url=str(item),
                description=f"Auto-discovered from {scan_path}",
                branch="main",
                owner_id=owner_id,
                local_path=str(item),
            )
            self.db.add(repo)
            await self.db.commit()

            # Reload from database to get all attributes
            result = await self.db.execute(
                select(Repository).where(Repository.id == repo.id)
            )
            repo = result.scalar_one()

            # Try to detect JDK version
            version = await self.detect_jdk_version(repo)
            if version:
                repo.current_jdk_version = version
                # Set a sensible target version (latest patch of same major)
                # e.g., 11.0.18 -> 11.0.22, 17.0.6 -> 17.0.10
                parts = version.split(".")
                if len(parts) >= 1:
                    major = parts[0]
                    # Default targets for common LTS versions
                    targets = {"8": "8.0.402", "11": "11.0.22", "17": "17.0.10", "21": "21.0.2"}
                    repo.target_jdk_version = targets.get(major, f"{major}.0.99")
                await self.db.commit()
                # Reload again
                result = await self.db.execute(
                    select(Repository).where(Repository.id == repo.id)
                )
                repo = result.scalar_one()

            discovered.append(repo)

        return discovered
