"""RAG service using Qdrant for JDK knowledge base."""

import asyncio
import hashlib
import logging
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class RAGService:
    """Service for RAG operations using Qdrant vector database."""

    COLLECTION_RELEASE_NOTES = "jdk_release_notes"
    COLLECTION_FIXES = "successful_fixes"
    COLLECTION_DOCS = "documentation"

    EMBEDDING_DIMENSIONS = 3072  # Gemini gemini-embedding-001

    def __init__(self):
        self.qdrant_url = getattr(settings, 'qdrant_url', 'http://localhost:6333')
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize Qdrant collections if they don't exist."""
        if self._initialized:
            return True

        try:
            # Create collections if they don't exist
            for collection_name in [
                self.COLLECTION_RELEASE_NOTES,
                self.COLLECTION_FIXES,
                self.COLLECTION_DOCS,
            ]:
                await self._ensure_collection(collection_name)

            self._initialized = True
            logger.info("[RAG] Qdrant collections initialized")
            return True

        except Exception as e:
            logger.warning(f"[RAG] Failed to initialize Qdrant: {e}")
            return False

    async def _ensure_collection(self, collection_name: str) -> bool:
        """Create a collection if it doesn't exist."""
        async with httpx.AsyncClient() as client:
            # Check if collection exists
            try:
                response = await client.get(
                    f"{self.qdrant_url}/collections/{collection_name}",
                    timeout=10.0
                )
                if response.status_code == 200:
                    logger.debug(f"[RAG] Collection {collection_name} exists")
                    return True
            except Exception:
                pass

            # Create collection
            try:
                response = await client.put(
                    f"{self.qdrant_url}/collections/{collection_name}",
                    json={
                        "vectors": {
                            "size": self.EMBEDDING_DIMENSIONS,
                            "distance": "Cosine"
                        }
                    },
                    timeout=30.0
                )
                if response.status_code in [200, 201]:
                    logger.info(f"[RAG] Created collection {collection_name}")
                    return True
                else:
                    logger.warning(f"[RAG] Failed to create collection: {response.text}")
                    return False
            except Exception as e:
                logger.warning(f"[RAG] Error creating collection: {e}")
                return False

    # -------------------------------------------------------------------------
    # Embedding Generation
    # -------------------------------------------------------------------------

    async def embed_text(self, text: str) -> list[float] | None:
        """Generate embedding using Gemini API."""
        if not settings.google_api_key:
            logger.warning("[RAG] No Google API key configured for embeddings")
            return None

        try:
            async with httpx.AsyncClient() as client:
                # Use gemini-embedding-001 model
                response = await client.post(
                    "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent",
                    params={"key": settings.google_api_key},
                    json={
                        "model": "models/gemini-embedding-001",
                        "content": {"parts": [{"text": text[:8000]}]},  # Truncate to limit
                    },
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["embedding"]["values"]
                else:
                    logger.warning(f"[RAG] Embedding failed: {response.status_code} {response.text}")
                    return None

        except Exception as e:
            logger.warning(f"[RAG] Embedding error: {e}")
            return None

    async def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        """Generate embeddings for multiple texts."""
        # Process in parallel with limit
        semaphore = asyncio.Semaphore(5)

        async def embed_one(text: str) -> list[float] | None:
            async with semaphore:
                return await self.embed_text(text)

        return await asyncio.gather(*[embed_one(t) for t in texts])

    # -------------------------------------------------------------------------
    # Release Notes Indexing
    # -------------------------------------------------------------------------

    async def index_release_note(
        self,
        version: str,
        change_type: str,
        description: str,
        affected_classes: list[str] | None = None,
        affected_methods: list[str] | None = None,
        cve_id: str | None = None,
        migration_notes: str | None = None,
    ) -> str | None:
        """Index a single JDK release note entry."""
        # Create searchable text
        search_text = f"""
        JDK {version} {change_type}:
        {description}
        Affected: {', '.join(affected_classes or [])} {', '.join(affected_methods or [])}
        {f'CVE: {cve_id}' if cve_id else ''}
        {f'Migration: {migration_notes}' if migration_notes else ''}
        """.strip()

        embedding = await self.embed_text(search_text)
        if not embedding:
            return None

        # Generate deterministic ID based on content
        point_id = hashlib.md5(f"{version}:{change_type}:{description[:100]}".encode()).hexdigest()

        payload = {
            "version": version,
            "change_type": change_type,
            "description": description,
            "affected_classes": affected_classes or [],
            "affected_methods": affected_methods or [],
            "cve_id": cve_id,
            "migration_notes": migration_notes,
            "search_text": search_text,
        }

        return await self._upsert_point(
            collection=self.COLLECTION_RELEASE_NOTES,
            point_id=point_id,
            vector=embedding,
            payload=payload,
        )

    async def index_release_notes_batch(
        self,
        changes: list[dict],
    ) -> dict:
        """Index multiple release note changes."""
        indexed = 0
        failed = 0

        for change in changes:
            result = await self.index_release_note(
                version=change.get("version", ""),
                change_type=change.get("change_type", ""),
                description=change.get("description", ""),
                affected_classes=change.get("affected_classes"),
                affected_methods=change.get("affected_methods"),
                cve_id=change.get("cve_id"),
                migration_notes=change.get("migration_notes"),
            )
            if result:
                indexed += 1
            else:
                failed += 1

        logger.info(f"[RAG] Indexed {indexed} release notes, {failed} failed")
        return {"indexed": indexed, "failed": failed}

    # -------------------------------------------------------------------------
    # Successful Fixes Indexing
    # -------------------------------------------------------------------------

    async def index_successful_fix(
        self,
        original_code: str,
        fixed_code: str,
        change_type: str,
        explanation: str,
        file_path: str | None = None,
        jdk_version: str | None = None,
    ) -> str | None:
        """Store a successful fix for future retrieval."""
        search_text = f"""
        {change_type} fix:
        Original: {original_code[:500]}
        Fixed: {fixed_code[:500]}
        Explanation: {explanation}
        """.strip()

        embedding = await self.embed_text(search_text)
        if not embedding:
            return None

        point_id = str(uuid4())

        payload = {
            "original_code": original_code,
            "fixed_code": fixed_code,
            "change_type": change_type,
            "explanation": explanation,
            "file_path": file_path,
            "jdk_version": jdk_version,
        }

        return await self._upsert_point(
            collection=self.COLLECTION_FIXES,
            point_id=point_id,
            vector=embedding,
            payload=payload,
        )

    # -------------------------------------------------------------------------
    # Documentation Indexing
    # -------------------------------------------------------------------------

    async def index_documentation(
        self,
        title: str,
        content: str,
        source_url: str,
        doc_type: str,  # "migration_guide", "api_doc", "jep", etc.
        jdk_versions: list[str] | None = None,
    ) -> str | None:
        """Index documentation content."""
        # Split long content into chunks
        chunks = self._chunk_text(content, max_length=2000)
        indexed = 0

        for i, chunk in enumerate(chunks):
            search_text = f"{title}\n{chunk}"
            embedding = await self.embed_text(search_text)
            if not embedding:
                continue

            point_id = hashlib.md5(f"{source_url}:{i}".encode()).hexdigest()

            payload = {
                "title": title,
                "content": chunk,
                "source_url": source_url,
                "doc_type": doc_type,
                "jdk_versions": jdk_versions or [],
                "chunk_index": i,
                "total_chunks": len(chunks),
            }

            if await self._upsert_point(
                collection=self.COLLECTION_DOCS,
                point_id=point_id,
                vector=embedding,
                payload=payload,
            ):
                indexed += 1

        return f"indexed_{indexed}_chunks" if indexed > 0 else None

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    async def search_release_notes(
        self,
        query: str,
        version_filter: str | None = None,
        change_type_filter: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """Search for relevant JDK release notes."""
        embedding = await self.embed_text(query)
        if not embedding:
            return []

        # Build filter
        filter_conditions = []
        if version_filter:
            filter_conditions.append({
                "key": "version",
                "match": {"value": version_filter}
            })
        if change_type_filter:
            filter_conditions.append({
                "key": "change_type",
                "match": {"value": change_type_filter}
            })

        qdrant_filter = None
        if filter_conditions:
            qdrant_filter = {"must": filter_conditions}

        return await self._search(
            collection=self.COLLECTION_RELEASE_NOTES,
            vector=embedding,
            filter=qdrant_filter,
            limit=limit,
        )

    async def search_similar_fixes(
        self,
        code_snippet: str,
        change_type: str | None = None,
        limit: int = 3,
    ) -> list[dict]:
        """Find similar past fixes for few-shot examples."""
        embedding = await self.embed_text(code_snippet)
        if not embedding:
            return []

        qdrant_filter = None
        if change_type:
            qdrant_filter = {
                "must": [{
                    "key": "change_type",
                    "match": {"value": change_type}
                }]
            }

        return await self._search(
            collection=self.COLLECTION_FIXES,
            vector=embedding,
            filter=qdrant_filter,
            limit=limit,
        )

    async def search_documentation(
        self,
        query: str,
        doc_type: str | None = None,
        jdk_version: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """Search documentation."""
        embedding = await self.embed_text(query)
        if not embedding:
            return []

        filter_conditions = []
        if doc_type:
            filter_conditions.append({
                "key": "doc_type",
                "match": {"value": doc_type}
            })
        if jdk_version:
            filter_conditions.append({
                "key": "jdk_versions",
                "match": {"any": [jdk_version]}
            })

        qdrant_filter = {"must": filter_conditions} if filter_conditions else None

        return await self._search(
            collection=self.COLLECTION_DOCS,
            vector=embedding,
            filter=qdrant_filter,
            limit=limit,
        )

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    async def _upsert_point(
        self,
        collection: str,
        point_id: str,
        vector: list[float],
        payload: dict,
    ) -> str | None:
        """Insert or update a point in Qdrant."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.qdrant_url}/collections/{collection}/points",
                    json={
                        "points": [{
                            "id": point_id,
                            "vector": vector,
                            "payload": payload,
                        }]
                    },
                    timeout=30.0
                )

                if response.status_code in [200, 201]:
                    return point_id
                else:
                    logger.warning(f"[RAG] Upsert failed: {response.text}")
                    return None

        except Exception as e:
            logger.warning(f"[RAG] Upsert error: {e}")
            return None

    async def _search(
        self,
        collection: str,
        vector: list[float],
        filter: dict | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """Search for similar vectors in Qdrant."""
        try:
            async with httpx.AsyncClient() as client:
                body: dict[str, Any] = {
                    "vector": vector,
                    "limit": limit,
                    "with_payload": True,
                }
                if filter:
                    body["filter"] = filter

                response = await client.post(
                    f"{self.qdrant_url}/collections/{collection}/points/search",
                    json=body,
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    results = []
                    for hit in data.get("result", []):
                        result = hit.get("payload", {})
                        result["_score"] = hit.get("score", 0)
                        result["_id"] = hit.get("id")
                        results.append(result)
                    return results
                else:
                    logger.warning(f"[RAG] Search failed: {response.text}")
                    return []

        except Exception as e:
            logger.warning(f"[RAG] Search error: {e}")
            return []

    def _chunk_text(self, text: str, max_length: int = 2000) -> list[str]:
        """Split text into chunks."""
        if len(text) <= max_length:
            return [text]

        chunks = []
        paragraphs = text.split("\n\n")
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= max_length:
                current_chunk += ("\n\n" if current_chunk else "") + para
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = para[:max_length]

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    async def get_stats(self) -> dict:
        """Get statistics about indexed content."""
        stats = {}

        for collection_name in [
            self.COLLECTION_RELEASE_NOTES,
            self.COLLECTION_FIXES,
            self.COLLECTION_DOCS,
        ]:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.qdrant_url}/collections/{collection_name}",
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        data = response.json()
                        stats[collection_name] = {
                            "points_count": data.get("result", {}).get("points_count", 0),
                            "status": data.get("result", {}).get("status", "unknown"),
                        }
                    else:
                        stats[collection_name] = {"error": "not found"}
            except Exception as e:
                stats[collection_name] = {"error": str(e)}

        return stats


# Global instance
rag_service = RAGService()
