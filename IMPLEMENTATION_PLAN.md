# Implementation Plan: Tracing, Stability & RAG

## Overview

This plan covers three major improvements:
1. **Phase 1 - Stability**: Syntax validation, rollback, error handling
2. **Phase 2 - Tracing**: Full agent observability with real-time UI
3. **Phase 3 - RAG**: JDK knowledge base with Qdrant

---

## Phase 1: Stability (Minimal)

### 1.1 Syntax Validation Before Patch Apply

**Goal**: Verify Java code compiles before writing to disk

**Files to modify**:
- `backend/app/services/llm_service.py` - Add `validate_java_syntax()`
- `backend/app/agents/patcher_agent.py` - Call validation before apply

**Implementation**:
```python
# llm_service.py
async def validate_java_syntax(self, code: str, file_path: str) -> dict:
    """Quick syntax check using javac -d /dev/null"""
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(suffix='.java', delete=False) as f:
        f.write(code.encode())
        temp_path = f.name

    result = subprocess.run(
        ['javac', '-d', '/dev/null', temp_path],
        capture_output=True, text=True
    )

    return {
        "valid": result.returncode == 0,
        "errors": result.stderr if result.returncode != 0 else None
    }
```

### 1.2 Git Stash Rollback

**Goal**: Auto-restore on patch failure

**Files to modify**:
- `backend/app/agents/patcher_agent.py` - Add stash/restore around patch apply

**Implementation**:
```python
# Before applying patches
subprocess.run(['git', 'stash', 'push', '-m', 'pre-patch-backup'], cwd=repo_path)

# On failure
subprocess.run(['git', 'stash', 'pop'], cwd=repo_path)
```

### 1.3 Better Error Messages

**Goal**: User-friendly error explanations

**Files to modify**:
- `backend/app/agents/base.py` - Add `ErrorContext` dataclass
- All agents - Use structured errors

---

## Phase 2: Tracing & Observability

### 2.1 Database Schema

**New table**: `traces`

```sql
CREATE TABLE traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL,
    repository_id UUID REFERENCES repositories(id),
    user_id UUID REFERENCES users(id),
    status VARCHAR(20) DEFAULT 'running',  -- running, completed, failed
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE trace_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id UUID REFERENCES traces(id) ON DELETE CASCADE,
    agent VARCHAR(50) NOT NULL,
    event_type VARCHAR(30) NOT NULL,  -- decision, action, llm_call, error, info
    message TEXT NOT NULL,
    data JSONB DEFAULT '{}',
    timestamp TIMESTAMP DEFAULT NOW(),
    duration_ms INTEGER,
    parent_event_id UUID REFERENCES trace_events(id)
);

CREATE INDEX idx_trace_events_trace ON trace_events(trace_id);
CREATE INDEX idx_trace_events_agent ON trace_events(agent);
CREATE INDEX idx_traces_workflow ON traces(workflow_id);
```

### 2.2 TraceService

**New file**: `backend/app/services/trace_service.py`

```python
class TraceService:
    async def start_trace(workflow_id: UUID, repo_id: UUID, user_id: UUID) -> Trace
    async def end_trace(trace_id: UUID, status: str) -> None
    async def log_event(trace_id: UUID, agent: str, event_type: str, message: str, data: dict) -> TraceEvent
    async def log_decision(trace_id: UUID, agent: str, decision: str, reason: str, confidence: float) -> TraceEvent
    async def log_llm_call(trace_id: UUID, agent: str, provider: str, tokens_in: int, tokens_out: int, latency_ms: int) -> TraceEvent
    async def get_trace(trace_id: UUID) -> Trace
    async def get_events(trace_id: UUID) -> list[TraceEvent]
```

### 2.3 WebSocket Endpoint

**New file**: `backend/app/api/routes/traces.py`

```python
@router.websocket("/ws/traces/{workflow_id}")
async def trace_websocket(websocket: WebSocket, workflow_id: UUID):
    await websocket.accept()
    # Subscribe to trace events for this workflow
    # Broadcast events as they happen
```

### 2.4 Agent Instrumentation

**Modify**: All agents to emit trace events

```python
# In each agent's execute() method
await trace_service.log_event(
    trace_id=context.trace_id,
    agent=self.name,
    event_type="action",
    message=f"Starting {action}",
    data={"params": kwargs}
)
```

### 2.5 Frontend Components

**New files**:
- `frontend/src/components/trace/ActivityFeed.tsx` - Real-time event stream
- `frontend/src/components/trace/TraceTimeline.tsx` - Visual timeline
- `frontend/src/components/trace/DecisionTree.tsx` - Decision explanations
- `frontend/src/hooks/useTrace.ts` - WebSocket connection hook

### 2.6 UI Integration

**Modify**: `frontend/src/components/dashboard/RepositoryDetail.tsx`
- Add ActivityFeed panel alongside workflow steps
- Show real-time agent activity during execution

---

## Phase 3: RAG with Qdrant

### 3.1 Docker Setup

**Modify**: `docker-compose.yml`

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      - QDRANT__SERVICE__GRPC_PORT=6334

volumes:
  qdrant_data:
```

### 3.2 Configuration

**Modify**: `backend/app/core/config.py`

```python
# RAG / Qdrant
qdrant_url: str = "http://localhost:6333"
qdrant_collection_release_notes: str = "jdk_release_notes"
qdrant_collection_fixes: str = "successful_fixes"
embedding_model: str = "text-embedding-004"  # Gemini
embedding_dimensions: int = 768
```

### 3.3 RAG Service

**New file**: `backend/app/services/rag_service.py`

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

class RAGService:
    def __init__(self):
        self.client = QdrantClient(url=settings.qdrant_url)
        self._ensure_collections()

    def _ensure_collections(self):
        """Create collections if they don't exist."""
        # jdk_release_notes collection
        # successful_fixes collection

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding using Gemini."""

    async def index_release_notes(self, version: str, changes: list[JDKChange]) -> int:
        """Index JDK release notes for a version."""

    async def index_successful_fix(self, original: str, fixed: str, change_type: str, explanation: str) -> None:
        """Store a successful fix for future retrieval."""

    async def search_similar_changes(self, query: str, limit: int = 5) -> list[dict]:
        """Find similar JDK changes for context."""

    async def search_similar_fixes(self, code_snippet: str, change_type: str, limit: int = 3) -> list[dict]:
        """Find similar past fixes for few-shot examples."""
```

### 3.4 JDK Release Notes Ingestion

**New file**: `backend/app/services/rag_ingestion_service.py`

```python
class RAGIngestionService:
    async def ingest_jdk_release_notes(self, from_version: str, to_version: str) -> dict:
        """Fetch and index release notes for version range."""

    async def ingest_migration_guides(self) -> dict:
        """Index official Oracle/OpenJDK migration guides."""

    async def ingest_from_url(self, url: str, doc_type: str) -> dict:
        """Index content from a URL (docs, guides, etc.)."""
```

### 3.5 Integration with Analyzer

**Modify**: `backend/app/services/analyzer_service.py`

```python
async def _analyze_file_with_llm(self, ...):
    # Query RAG for relevant JDK changes
    rag_context = await rag_service.search_similar_changes(
        query=f"JDK {from_version} to {to_version} compatibility",
        limit=10
    )

    # Add RAG context to LLM prompt
    messages[0]["content"] += f"\n\nRelevant JDK changes from knowledge base:\n{rag_context}"
```

### 3.6 Integration with Fixer

**Modify**: `backend/app/agents/fixer_agent.py`

```python
async def fix_one(impact, index):
    # Search for similar past fixes
    similar_fixes = await rag_service.search_similar_fixes(
        code_snippet=impact.get("code_snippet"),
        change_type=impact.get("change_type"),
        limit=3
    )

    # Use as few-shot examples in LLM prompt
    if similar_fixes:
        examples = format_few_shot_examples(similar_fixes)
        # Add to prompt...
```

### 3.7 API Endpoints

**New routes in**: `backend/app/api/routes/rag.py`

```python
@router.post("/rag/ingest/release-notes")
async def ingest_release_notes(from_version: str, to_version: str)

@router.post("/rag/ingest/url")
async def ingest_url(url: str, doc_type: str)

@router.get("/rag/search")
async def search_knowledge_base(query: str, collection: str, limit: int = 5)

@router.get("/rag/stats")
async def get_rag_stats()
```

### 3.8 Frontend RAG Panel

**New files**:
- `frontend/src/components/rag/KnowledgeBasePanel.tsx` - View indexed content
- `frontend/src/components/rag/IngestionForm.tsx` - Add new content

---

## Implementation Order

### Week 1: Foundation
1. [x] Fix patch corruption issues (DONE)
2. [ ] Add syntax validation before patch apply
3. [ ] Add git stash rollback
4. [ ] Create trace database schema + migration
5. [ ] Implement TraceService

### Week 2: Tracing Backend
6. [ ] Instrument all agents with trace events
7. [ ] Add WebSocket endpoint for real-time events
8. [ ] Add LLM call tracing (tokens, latency)
9. [ ] Create trace API endpoints

### Week 3: Tracing Frontend
10. [ ] Create ActivityFeed component
11. [ ] Create TraceTimeline component
12. [ ] Integrate into RepositoryDetail
13. [ ] Add trace history viewer

### Week 4: RAG Setup
14. [ ] Add Qdrant to docker-compose
15. [ ] Implement RAGService with embeddings
16. [ ] Create ingestion service
17. [ ] Ingest JDK 11-21 release notes

### Week 5: RAG Integration
18. [ ] Integrate RAG into analyzer
19. [ ] Integrate RAG into fixer (few-shot)
20. [ ] Add RAG API endpoints
21. [ ] Create frontend RAG panel

### Week 6: Polish
22. [ ] Performance optimization
23. [ ] Error handling improvements
24. [ ] Documentation
25. [ ] Testing

---

## File Summary

### New Files
```
backend/app/services/trace_service.py
backend/app/services/rag_service.py
backend/app/services/rag_ingestion_service.py
backend/app/models/trace.py
backend/app/schemas/trace.py
backend/app/api/routes/traces.py
backend/app/api/routes/rag.py
backend/alembic/versions/xxx_add_traces.py
frontend/src/components/trace/ActivityFeed.tsx
frontend/src/components/trace/TraceTimeline.tsx
frontend/src/components/trace/DecisionTree.tsx
frontend/src/components/rag/KnowledgeBasePanel.tsx
frontend/src/hooks/useTrace.ts
```

### Modified Files
```
docker-compose.yml (add Qdrant)
backend/app/core/config.py (add RAG settings)
backend/app/main.py (add trace routes)
backend/app/agents/*.py (add tracing)
backend/app/services/analyzer_service.py (RAG integration)
backend/app/services/llm_service.py (syntax validation, LLM tracing)
frontend/src/components/dashboard/RepositoryDetail.tsx (add trace panel)
frontend/src/services/api.ts (add trace/RAG endpoints)
```
