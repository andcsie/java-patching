"""Service for ingesting JDK release notes and documentation into RAG."""

import logging
import re

import httpx

from app.services.rag_service import rag_service
from app.services.release_notes_service import release_notes_service

logger = logging.getLogger(__name__)


class RAGIngestionService:
    """Service for ingesting JDK knowledge into Qdrant."""

    # JDK versions to index
    SUPPORTED_VERSIONS = [
        "11.0.18", "11.0.19", "11.0.20", "11.0.21", "11.0.22", "11.0.23", "11.0.24",
        "17.0.6", "17.0.7", "17.0.8", "17.0.9", "17.0.10", "17.0.11", "17.0.12",
        "21.0.1", "21.0.2", "21.0.3", "21.0.4",
    ]

    # Migration guide URLs
    MIGRATION_GUIDES = [
        {
            "title": "JDK 11 Migration Guide",
            "url": "https://docs.oracle.com/en/java/javase/11/migrate/getting-started.html",
            "jdk_versions": ["11"],
        },
        {
            "title": "JDK 17 Migration Guide",
            "url": "https://docs.oracle.com/en/java/javase/17/migrate/getting-started.html",
            "jdk_versions": ["17"],
        },
        {
            "title": "JDK 21 Migration Guide",
            "url": "https://docs.oracle.com/en/java/javase/21/migrate/getting-started.html",
            "jdk_versions": ["21"],
        },
    ]

    async def ingest_all_release_notes(self) -> dict:
        """Ingest release notes for all supported JDK versions."""
        await rag_service.initialize()

        total_indexed = 0
        total_failed = 0
        versions_processed = []

        for version in self.SUPPORTED_VERSIONS:
            logger.info(f"[RAG Ingestion] Processing JDK {version}...")
            try:
                # Fetch release notes
                changes = await release_notes_service.get_changes_for_version(version)

                if not changes:
                    logger.info(f"[RAG Ingestion] No changes found for JDK {version}")
                    continue

                # Convert to dict format for indexing
                changes_data = [
                    {
                        "version": change.version,
                        "change_type": change.change_type.value if hasattr(change.change_type, 'value') else str(change.change_type),
                        "description": change.description,
                        "affected_classes": change.affected_classes,
                        "affected_methods": change.affected_methods,
                        "cve_id": change.cve_id,
                        "migration_notes": change.migration_notes,
                    }
                    for change in changes
                ]

                result = await rag_service.index_release_notes_batch(changes_data)
                total_indexed += result["indexed"]
                total_failed += result["failed"]
                versions_processed.append(version)

            except Exception as e:
                logger.warning(f"[RAG Ingestion] Failed to process JDK {version}: {e}")
                total_failed += 1

        logger.info(f"[RAG Ingestion] Complete: {total_indexed} indexed, {total_failed} failed")

        return {
            "indexed": total_indexed,
            "failed": total_failed,
            "versions_processed": versions_processed,
        }

    async def ingest_version_range(
        self,
        from_version: str,
        to_version: str,
    ) -> dict:
        """Ingest release notes for a specific version range."""
        await rag_service.initialize()

        logger.info(f"[RAG Ingestion] Processing JDK {from_version} to {to_version}...")

        try:
            changes = await release_notes_service.get_changes_between_versions(
                from_version,
                to_version,
            )

            if not changes:
                return {"indexed": 0, "failed": 0, "message": "No changes found"}

            changes_data = [
                {
                    "version": change.version,
                    "change_type": change.change_type.value if hasattr(change.change_type, 'value') else str(change.change_type),
                    "description": change.description,
                    "affected_classes": change.affected_classes,
                    "affected_methods": change.affected_methods,
                    "cve_id": change.cve_id,
                    "migration_notes": change.migration_notes,
                }
                for change in changes
            ]

            result = await rag_service.index_release_notes_batch(changes_data)

            return {
                "indexed": result["indexed"],
                "failed": result["failed"],
                "from_version": from_version,
                "to_version": to_version,
            }

        except Exception as e:
            logger.error(f"[RAG Ingestion] Failed: {e}")
            return {"indexed": 0, "failed": 1, "error": str(e)}

    async def ingest_url(
        self,
        url: str,
        title: str | None = None,
        doc_type: str = "documentation",
        jdk_versions: list[str] | None = None,
    ) -> dict:
        """Ingest content from a URL."""
        await rag_service.initialize()

        logger.info(f"[RAG Ingestion] Fetching {url}...")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0, follow_redirects=True)
                response.raise_for_status()
                content = response.text

            # Extract title if not provided
            if not title:
                title_match = re.search(r'<title>([^<]+)</title>', content, re.IGNORECASE)
                title = title_match.group(1) if title_match else url

            # Clean HTML to text
            text_content = self._html_to_text(content)

            if not text_content or len(text_content) < 100:
                return {"indexed": 0, "error": "No meaningful content found"}

            result = await rag_service.index_documentation(
                title=title,
                content=text_content,
                source_url=url,
                doc_type=doc_type,
                jdk_versions=jdk_versions,
            )

            return {
                "indexed": 1 if result else 0,
                "url": url,
                "title": title,
                "content_length": len(text_content),
            }

        except Exception as e:
            logger.error(f"[RAG Ingestion] Failed to fetch {url}: {e}")
            return {"indexed": 0, "error": str(e)}

    async def ingest_migration_guides(self) -> dict:
        """Ingest official Oracle migration guides."""
        total_indexed = 0
        results = []

        for guide in self.MIGRATION_GUIDES:
            result = await self.ingest_url(
                url=guide["url"],
                title=guide["title"],
                doc_type="migration_guide",
                jdk_versions=guide["jdk_versions"],
            )
            results.append(result)
            total_indexed += result.get("indexed", 0)

        return {
            "total_indexed": total_indexed,
            "guides": results,
        }

    async def ingest_custom_knowledge(
        self,
        entries: list[dict],
    ) -> dict:
        """Ingest custom knowledge entries."""
        await rag_service.initialize()

        indexed = 0
        failed = 0

        for entry in entries:
            entry_type = entry.get("type", "release_note")

            try:
                if entry_type == "release_note":
                    result = await rag_service.index_release_note(
                        version=entry.get("version", ""),
                        change_type=entry.get("change_type", ""),
                        description=entry.get("description", ""),
                        affected_classes=entry.get("affected_classes"),
                        affected_methods=entry.get("affected_methods"),
                        cve_id=entry.get("cve_id"),
                        migration_notes=entry.get("migration_notes"),
                    )
                elif entry_type == "fix":
                    result = await rag_service.index_successful_fix(
                        original_code=entry.get("original_code", ""),
                        fixed_code=entry.get("fixed_code", ""),
                        change_type=entry.get("change_type", ""),
                        explanation=entry.get("explanation", ""),
                        file_path=entry.get("file_path"),
                        jdk_version=entry.get("jdk_version"),
                    )
                else:
                    result = None

                if result:
                    indexed += 1
                else:
                    failed += 1

            except Exception as e:
                logger.warning(f"[RAG Ingestion] Entry failed: {e}")
                failed += 1

        return {"indexed": indexed, "failed": failed}

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text."""
        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # Remove HTML comments
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)

        # Replace common block elements with newlines
        html = re.sub(r'<(br|p|div|h[1-6]|li|tr)[^>]*>', '\n', html, flags=re.IGNORECASE)

        # Remove all remaining tags
        html = re.sub(r'<[^>]+>', '', html)

        # Decode HTML entities
        html = html.replace('&nbsp;', ' ')
        html = html.replace('&amp;', '&')
        html = html.replace('&lt;', '<')
        html = html.replace('&gt;', '>')
        html = html.replace('&quot;', '"')

        # Clean up whitespace
        lines = [line.strip() for line in html.split('\n')]
        lines = [line for line in lines if line]
        text = '\n'.join(lines)

        # Remove excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()


# Global instance
rag_ingestion_service = RAGIngestionService()
