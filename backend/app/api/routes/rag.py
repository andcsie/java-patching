"""API routes for RAG knowledge base."""

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.rag_ingestion_service import rag_ingestion_service
from app.services.rag_service import rag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])


# -------------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------------

class IngestVersionRangeRequest(BaseModel):
    from_version: str
    to_version: str


class IngestUrlRequest(BaseModel):
    url: str
    title: str | None = None
    doc_type: str = "documentation"
    jdk_versions: list[str] | None = None


class SearchRequest(BaseModel):
    query: str
    collection: Literal["release_notes", "fixes", "docs"] = "release_notes"
    limit: int = 5
    version_filter: str | None = None
    change_type_filter: str | None = None


class IngestCustomRequest(BaseModel):
    entries: list[dict]


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------

@router.get("/stats")
async def get_stats():
    """Get RAG knowledge base statistics."""
    try:
        stats = await rag_service.get_stats()
        return {
            "status": "ok",
            "collections": stats,
        }
    except Exception as e:
        logger.error(f"[RAG] Stats error: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


@router.post("/initialize")
async def initialize_rag():
    """Initialize RAG collections in Qdrant."""
    success = await rag_service.initialize()
    return {
        "status": "ok" if success else "error",
        "message": "Collections initialized" if success else "Failed to initialize",
    }


@router.post("/ingest/all-release-notes")
async def ingest_all_release_notes():
    """Ingest release notes for all supported JDK versions."""
    try:
        result = await rag_ingestion_service.ingest_all_release_notes()
        return {
            "status": "ok",
            **result,
        }
    except Exception as e:
        logger.error(f"[RAG] Ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/version-range")
async def ingest_version_range(request: IngestVersionRangeRequest):
    """Ingest release notes for a specific JDK version range."""
    try:
        result = await rag_ingestion_service.ingest_version_range(
            from_version=request.from_version,
            to_version=request.to_version,
        )
        return {
            "status": "ok",
            **result,
        }
    except Exception as e:
        logger.error(f"[RAG] Ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/url")
async def ingest_url(request: IngestUrlRequest):
    """Ingest content from a URL."""
    try:
        result = await rag_ingestion_service.ingest_url(
            url=request.url,
            title=request.title,
            doc_type=request.doc_type,
            jdk_versions=request.jdk_versions,
        )
        return {
            "status": "ok",
            **result,
        }
    except Exception as e:
        logger.error(f"[RAG] Ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/migration-guides")
async def ingest_migration_guides():
    """Ingest official Oracle JDK migration guides."""
    try:
        result = await rag_ingestion_service.ingest_migration_guides()
        return {
            "status": "ok",
            **result,
        }
    except Exception as e:
        logger.error(f"[RAG] Ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/custom")
async def ingest_custom(request: IngestCustomRequest):
    """Ingest custom knowledge entries."""
    try:
        result = await rag_ingestion_service.ingest_custom_knowledge(request.entries)
        return {
            "status": "ok",
            **result,
        }
    except Exception as e:
        logger.error(f"[RAG] Ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search(request: SearchRequest):
    """Search the knowledge base."""
    try:
        if request.collection == "release_notes":
            results = await rag_service.search_release_notes(
                query=request.query,
                version_filter=request.version_filter,
                change_type_filter=request.change_type_filter,
                limit=request.limit,
            )
        elif request.collection == "fixes":
            results = await rag_service.search_similar_fixes(
                code_snippet=request.query,
                change_type=request.change_type_filter,
                limit=request.limit,
            )
        elif request.collection == "docs":
            results = await rag_service.search_documentation(
                query=request.query,
                limit=request.limit,
            )
        else:
            results = []

        return {
            "status": "ok",
            "query": request.query,
            "collection": request.collection,
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        logger.error(f"[RAG] Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/release-notes")
async def search_release_notes(
    query: str = Query(..., min_length=2),
    version: str | None = Query(None),
    change_type: str | None = Query(None),
    limit: int = Query(5, ge=1, le=20),
):
    """Search JDK release notes."""
    try:
        results = await rag_service.search_release_notes(
            query=query,
            version_filter=version,
            change_type_filter=change_type,
            limit=limit,
        )
        return {
            "status": "ok",
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        logger.error(f"[RAG] Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/fixes")
async def search_fixes(
    code: str = Query(..., min_length=5),
    change_type: str | None = Query(None),
    limit: int = Query(3, ge=1, le=10),
):
    """Search for similar fixes."""
    try:
        results = await rag_service.search_similar_fixes(
            code_snippet=code,
            change_type=change_type,
            limit=limit,
        )
        return {
            "status": "ok",
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        logger.error(f"[RAG] Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
