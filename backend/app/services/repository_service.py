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
        repo = Repository(
            name=repo_data.name,
            url=repo_data.url,
            description=repo_data.description,
            branch=repo_data.branch,
            current_jdk_version=repo_data.current_jdk_version,
            target_jdk_version=repo_data.target_jdk_version,
            owner_id=owner_id,
        )
        self.db.add(repo)
        await self.db.commit()
        await self.db.refresh(repo)
        return repo

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

    async def clone(self, repo: Repository) -> str:
        """Clone a repository to local storage."""
        local_path = self.repos_base_path / str(repo.owner_id) / str(repo.id)

        # Ensure parent directory exists
        local_path.parent.mkdir(parents=True, exist_ok=True)

        # Clone in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._clone_sync,
            repo.url,
            local_path,
            repo.branch,
        )

        # Update repository with local path
        repo.local_path = str(local_path)
        await self.db.commit()

        return str(local_path)

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
