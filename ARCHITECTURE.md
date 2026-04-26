# Java Patching Application - Architecture

## Overview

The Java Patching Application is a comprehensive tool for analyzing and managing JDK version upgrades in Java projects. It features a **multi-agent architecture** where specialized agents handle different aspects of the upgrade workflow: analysis, fix generation, patch creation, testing, and PR management.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              External Clients                                │
├─────────────────┬───────────────────┬───────────────────┬───────────────────┤
│   Web Frontend  │   Claude Code     │  Claude Desktop   │   Other MCP       │
│   (React)       │   (MCP Client)    │  (MCP Client)     │   Clients         │
└────────┬────────┴─────────┬─────────┴─────────┬─────────┴─────────┬─────────┘
         │                  │                   │                   │
         │ REST API         │ MCP Protocol      │ MCP Protocol      │
         ▼                  ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Java Patching Backend                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐  │
│  │  FastAPI     │   │  FastMCP     │   │   Agent      │   │   LLM        │  │
│  │  REST API    │   │  Server      │   │   Registry   │   │   Service    │  │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘  │
│         │                  │                  │                  │          │
│         └──────────────────┴──────────────────┴──────────────────┘          │
│                                    │                                         │
│  ┌─────────────────────────────────┼─────────────────────────────────────┐  │
│  │                          Multi-Agent System                            │  │
│  │                                                                        │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐          │  │
│  │  │ Analysis   │ │  Fixer     │ │  Patcher   │ │Orchestrator│          │  │
│  │  │ Agent      │ │  Agent     │ │  Agent     │ │  Agent     │          │  │
│  │  │            │ │            │ │            │ │            │          │  │
│  │  │ • Impact   │ │ • Generate │ │ • Create   │ │ • Full     │          │  │
│  │  │   analysis │ │   fixes    │ │   patches  │ │   upgrade  │          │  │
│  │  │ • AST      │ │ • LLM-     │ │ • Run      │ │   pipeline │          │  │
│  │  │   parsing  │ │   powered  │ │   tests    │ │            │          │  │
│  │  │ • CVEs     │ │            │ │ • Create   │ │            │          │  │
│  │  │            │ │            │ │   PRs      │ │            │          │  │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘          │  │
│  │                                                                        │  │
│  │  ┌────────────┐ ┌────────────┐                                        │  │
│  │  │ Renovate   │ │ OpenRewrite│                                        │  │
│  │  │ Agent      │ │ Agent      │                                        │  │
│  │  │            │ │            │                                        │  │
│  │  │ • Version  │ │ • Major    │                                        │  │
│  │  │   detect   │ │   version  │                                        │  │
│  │  │ • Patch    │ │   migrate  │                                        │  │
│  │  │   discovery│ │ • Recipes  │                                        │  │
│  │  └────────────┘ └────────────┘                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                          Core Services                                 │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │  │
│  │  │  Analyzer    │  │  Repository  │  │  Release     │  │  Audit     │ │  │
│  │  │  Service     │  │  Service     │  │  Notes Svc   │  │  Service   │ │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘ │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└──────────────────────────────────┬───────────────────────────────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────────┐
         │                         │                             │
         ▼                         ▼                             ▼
┌─────────────────┐     ┌─────────────────┐           ┌─────────────────┐
│   PostgreSQL    │     │     Redis       │           │   LLM APIs      │
│   (persistence) │     │   (caching/     │           │ (Gemini/OpenAI/ │
│                 │     │    sessions)    │           │  Claude/Ollama) │
└─────────────────┘     └─────────────────┘           └─────────────────┘
```

## Upgrade Workflow

The application provides a 5-step workflow for JDK upgrades:

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│    1    │    │    2    │    │    3    │    │    4    │    │    5    │
│ ANALYZE │───▶│   FIX   │───▶│  PATCH  │───▶│  TEST   │───▶│   PR    │
│         │    │         │    │         │    │         │    │         │
│ Find    │    │ Generate│    │ Create  │    │ Run     │    │ Create  │
│ impacts │    │ LLM     │    │ unified │    │ Maven/  │    │ branch  │
│ in code │    │ fixes   │    │ diffs   │    │ Gradle  │    │ & push  │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
     │              │              │              │              │
     ▼              ▼              ▼              ▼              ▼
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│Analysis │    │ Fixer   │    │ Patcher │    │ Patcher │    │ Patcher │
│ Agent   │    │ Agent   │    │ Agent   │    │ Agent   │    │ Agent   │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
```

### Workflow Details

1. **Analyze** (Analysis Agent)
   - Fetches JDK release notes between versions
   - Parses Java files using tree-sitter AST
   - Identifies deprecated/removed APIs
   - Calculates risk score

2. **Fix** (Fixer Agent)
   - Takes impacts from analysis
   - Uses LLM to generate code fixes
   - Validates fix syntax
   - Supports batching for large codebases

3. **Patch** (Patcher Agent)
   - Creates unified diffs from fixes
   - Full line replacement (not partial)
   - Handles multi-line changes

4. **Test** (Patcher Agent)
   - Detects build tool (Maven/Gradle)
   - Runs test suite
   - Reports pass/fail status
   - Must pass before PR creation

5. **PR** (Patcher Agent)
   - Creates feature branch
   - Applies all patches
   - Commits changes
   - Pushes to remote
   - Creates PR via `gh` CLI or provides manual URL

## Core Agents

### Analysis Agent

Performs impact analysis using AST parsing:

```
┌─────────────────────────────────────────────────────────────────┐
│                       Analysis Agent                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Actions:                                                        │
│  ├── analyze_impact       Full AST-based impact analysis        │
│  ├── explain_impacts      Add LLM explanations                  │
│  ├── get_release_notes    Fetch JDK release notes               │
│  ├── get_security_advisories  Get CVEs between versions         │
│  └── suggest_upgrade_path     Recommend upgrade strategy        │
│                                                                  │
│  Process:                                                        │
│  1. Fetch release notes from OpenJDK/Adoptium                   │
│  2. Parse Java files with tree-sitter                           │
│  3. Match code against deprecated/removed APIs                  │
│  4. Calculate risk score (0-100)                                │
│  5. Generate severity levels (low/medium/high/critical)         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Fixer Agent

Generates AI-powered code fixes:

```
┌─────────────────────────────────────────────────────────────────┐
│                         Fixer Agent                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Actions:                                                        │
│  ├── generate_fixes       Generate fixes for all impacts        │
│  ├── generate_single_fix  Fix one impact                        │
│  └── validate_fix         Validate generated fix                │
│                                                                  │
│  Features:                                                       │
│  • Batching support (limit/offset)                              │
│  • Multiple LLM provider support                                │
│  • Returns complete replacement lines                           │
│  • Includes explanation for each fix                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Patcher Agent

Creates patches and manages Git/PR workflow:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Patcher Agent                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Actions:                                                        │
│  ├── create_patches       Generate unified diffs                │
│  ├── apply_all_patches    Apply patches to files                │
│  ├── run_tests            Run Maven/Gradle tests                │
│  └── create_pr            Full PR workflow                      │
│                                                                  │
│  PR Workflow:                                                    │
│  1. Create feature branch (jdk-upgrade/from-to/timestamp)       │
│  2. Apply all patches (direct file write)                       │
│  3. Stage and commit changes                                    │
│  4. Push to remote (if enabled)                                 │
│  5. Create PR via gh/bb/glab CLI                                │
│  6. Return manual PR URL if CLI not available                   │
│                                                                  │
│  Supported Remotes:                                              │
│  • GitHub (gh CLI)                                              │
│  • Bitbucket (bb CLI)                                           │
│  • GitLab (glab CLI)                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Renovate Agent

Patch-level JDK version management:

```
┌─────────────────────────────────────────────────────────────────┐
│                       Renovate Agent                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Actions:                                                        │
│  ├── detect_version       Detect JDK from build files           │
│  ├── get_available_patches Query Adoptium for updates           │
│  ├── preview_version_bump  Show diffs before applying           │
│  ├── apply_version_bump    Update version in files              │
│  └── generate_config       Create renovate.json                 │
│                                                                  │
│  Supported Files:                                                │
│  ├── pom.xml              (java.version, compiler.source/target)│
│  ├── build.gradle         (sourceCompatibility, targetCompat)   │
│  ├── build.gradle.kts     (same as build.gradle)                │
│  ├── .java-version        (jenv)                                │
│  ├── .sdkmanrc            (SDKMAN)                              │
│  └── .tool-versions       (asdf)                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### OpenRewrite Agent

Major version migrations with recipes:

```
┌─────────────────────────────────────────────────────────────────┐
│                     OpenRewrite Agent                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Actions:                                                        │
│  ├── list_recipes         List available migration recipes      │
│  ├── analyze_migration    Dry-run analysis of changes           │
│  ├── run_recipe           Execute transformation recipe         │
│  ├── suggest_migration_path Recommend upgrade steps             │
│  └── scan_security        OWASP Top 10 scanning                 │
│                                                                  │
│  Available Recipes:                                              │
│  ├── java8to11           Java 8 → 11 migration                  │
│  ├── java11to17          Java 11 → 17 migration                 │
│  ├── java17to21          Java 17 → 21 migration                 │
│  ├── jakarta_ee9         javax.* → jakarta.* namespace          │
│  ├── spring_boot_3       Spring Boot 2.x → 3.0                  │
│  ├── junit5              JUnit 4 → 5 migration                  │
│  └── security_fixes      OWASP security fixes                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Orchestrator Agent

Automated full upgrade pipeline:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Orchestrator Agent                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Actions:                                                        │
│  └── full_upgrade         Complete automated upgrade             │
│                                                                  │
│  Pipeline:                                                       │
│  1. Analysis Agent: analyze_impact                              │
│  2. Fixer Agent: generate_fixes                                 │
│  3. Patcher Agent: create_patches                               │
│  4. Patcher Agent: run_tests                                    │
│  5. Patcher Agent: create_pr (if tests pass)                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Multi-LLM Service

Unified interface with **Gemini as the default** provider:

```python
LLMService
├── GeminiProvider      # Default - Gemini 2.5 Flash (cost-efficient)
├── OpenAIProvider      # GPT-4, GPT-4 Turbo
├── AnthropicProvider   # Claude 3.5 Sonnet, Claude 3 Opus
└── OllamaProvider      # Self-hosted (Llama 3, Mistral, etc.)
```

**LLM Use Cases:**
- Impact explanation generation
- Code fix generation
- Migration plan suggestions
- Security advisory analysis

## Repository Service

Handles Git operations:

```python
RepositoryService
├── clone()              # Clone repository (HTTPS or SSH)
├── pull()               # Pull latest changes
├── detect_jdk_version() # Scan build files
└── scan_and_discover()  # Auto-discover Java projects

# SSH URL Conversion
# HTTPS URLs are automatically converted to SSH if needed:
# https://github.com/user/repo.git → git@github.com:user/repo.git
```

## API Structure

```
/api
├── /auth
│   ├── POST /register
│   ├── POST /login
│   └── GET  /me
│
├── /repositories
│   ├── GET    /              # List repositories
│   ├── POST   /              # Create repository
│   ├── GET    /{id}          # Get repository
│   ├── PATCH  /{id}          # Update repository
│   ├── DELETE /{id}          # Delete repository
│   ├── POST   /{id}/clone    # Clone repository
│   ├── POST   /{id}/pull     # Pull changes
│   ├── GET    /{id}/detect-version
│   └── POST   /scan          # Scan directory for projects
│
├── /agents
│   ├── GET  /                # List agents
│   ├── GET  /{name}          # Get agent details
│   ├── GET  /{name}/actions  # List agent actions
│   ├── POST /{name}/execute/{action}  # Execute action
│   ├── GET  /health          # Health check
│   └── GET  /llm/providers   # Available LLM providers
│
├── /analyses
│   ├── GET  /                # List analyses
│   └── GET  /{id}            # Get analysis details
│
└── /audit
    └── GET /logs             # Audit trail
```

## Frontend Architecture

React-based SPA with TypeScript:

```
frontend/src/
├── components/
│   ├── auth/              # Login, registration
│   ├── dashboard/
│   │   ├── RepositoryList.tsx
│   │   └── RepositoryDetail.tsx  # Main workflow UI
│   └── analysis/
│       ├── RiskBadge.tsx
│       └── DiffViewer.tsx
├── hooks/
│   ├── useAuth.ts
│   ├── useAnalysis.ts
│   └── useLLMProvider.ts
├── services/
│   └── api.ts             # API client
└── App.tsx
```

**Key Features:**
- 5-step workflow visualization
- Real-time agent execution status
- Diff viewer for patches
- Batch processing controls
- Push/PR toggle options

## Project Structure

```
JavaPatching/
├── backend/
│   ├── app/
│   │   ├── agents/                    # Multi-agent system
│   │   │   ├── base.py               # Agent base classes
│   │   │   ├── registry.py           # Agent registry
│   │   │   ├── bus.py                # Agent message bus
│   │   │   ├── analysis_agent.py     # Impact analysis
│   │   │   ├── fixer_agent.py        # Fix generation
│   │   │   ├── patcher_agent.py      # Patches & PRs
│   │   │   ├── renovate_agent.py     # Version management
│   │   │   ├── openrewrite_agent.py  # Major migrations
│   │   │   └── orchestrator_agent.py # Full pipeline
│   │   ├── api/routes/
│   │   ├── core/
│   │   │   ├── config.py             # Settings
│   │   │   ├── database.py           # Async SQLAlchemy
│   │   │   └── security.py           # JWT auth
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── llm_service.py        # Multi-LLM support
│   │   │   ├── repository_service.py # Git operations
│   │   │   ├── analyzer_service.py   # AST analysis
│   │   │   └── audit_service.py      # Audit logging
│   │   └── mcp/
│   │       └── server.py             # FastMCP server
│   ├── alembic/
│   ├── mcp_server.py
│   └── .env.example
│
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
│
├── docker-compose.yml
├── docker-compose.dev.yml
├── mcp-config.json
├── README.md
└── ARCHITECTURE.md
```

## Security Considerations

1. **Authentication**: JWT with configurable expiration
2. **Authorization**: User-scoped repositories
3. **Git Security**: SSH key support, no credential storage
4. **Audit Trail**: All actions logged
5. **Input Validation**: Pydantic schemas
6. **SQL Injection**: SQLAlchemy ORM

## Deployment

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
REDIS_URL=redis://host:6379

# Auth
SECRET_KEY=<random-secret>

# LLM Providers
GOOGLE_API_KEY=...              # Recommended
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_BASE_URL=http://localhost:11434

# Repository Storage
REPOS_BASE_PATH=/app/repos
REPOS_SCAN_PATH=/projects
```

### Docker Compose

```yaml
services:
  frontend:     # React on Vite (port 5173/3000)
  backend:      # FastAPI (port 8000)
  db:           # PostgreSQL 16 (port 5432)
  redis:        # Redis 7 (port 6379)
  ollama:       # Optional self-hosted LLM (port 11434)
```

## Extensibility

### Adding a New Agent

```python
from app.agents.base import Agent, AgentAction, AgentCapability
from app.agents.registry import register_agent

@register_agent
class MyCustomAgent(Agent):
    name = "my_agent"
    description = "Custom agent"
    version = "1.0.0"

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [AgentCapability.IMPACT_ANALYSIS]

    @property
    def actions(self) -> list[AgentAction]:
        return [
            AgentAction(
                name="my_action",
                description="Does something",
                parameters={...},
            ),
        ]

    async def execute(self, action: str, context: AgentContext, **kwargs) -> AgentResult:
        # Implementation
        ...
```

### Adding a New LLM Provider

```python
class MyProvider(LLMProvider):
    async def complete(self, messages: list[dict], **kwargs) -> str:
        ...

    async def stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        ...

# Register in LLMService._initialize_providers()
```
