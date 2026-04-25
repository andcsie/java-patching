# Java Patching Application - Architecture

## Overview

The Java Patching Application is a comprehensive tool for analyzing and managing JDK version upgrades in Java projects. It features a **multi-agent architecture** where specialized agents (Renovate, OpenRewrite) handle different aspects of version management and code transformation.

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
│  │  ┌──────────────────────────────────────────────────────────────────┐ │  │
│  │  │                         Agent Registry                            │ │  │
│  │  └──────────────────────────────────────────────────────────────────┘ │  │
│  │           │                         │                         │        │  │
│  │  ┌────────▼───────┐       ┌────────▼───────┐       ┌─────────▼──────┐ │  │
│  │  │  Renovate      │       │  OpenRewrite   │       │   Future       │ │  │
│  │  │  Agent         │       │  Agent         │       │   Agents...    │ │  │
│  │  │                │       │                │       │                │ │  │
│  │  │  • Patch       │       │  • Major       │       │  • Dependency  │ │  │
│  │  │    discovery   │       │    version     │       │    analysis    │ │  │
│  │  │  • Version     │       │    migrations  │       │  • CI/CD       │ │  │
│  │  │    bumping     │       │  • Recipe      │       │  • Custom      │ │  │
│  │  │  • Config gen  │       │    execution   │       │                │ │  │
│  │  └────────────────┘       └────────────────┘       └────────────────┘ │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                          Core Services                                 │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │  │
│  │  │  Analyzer    │  │  Renovate    │  │  Release     │  │  Audit     │ │  │
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

## Core Components

### 1. Multi-Agent System

The application uses a pluggable agent architecture where each agent specializes in a particular domain:

```python
# Agent Capabilities
AgentCapability
├── VERSION_DETECTION      # Detect JDK version from build files
├── PATCH_DISCOVERY        # Find available patch versions
├── VERSION_BUMPING        # Update version in build files
├── CODE_MIGRATION         # Major version code transformations
├── RECIPE_EXECUTION       # Run OpenRewrite recipes
├── REFACTORING            # Code refactoring
├── IMPACT_ANALYSIS        # Analyze upgrade impacts
├── SECURITY_SCANNING      # Security vulnerability detection
├── CONFIG_GENERATION      # Generate tool configs
└── BUILD_TOOL_SUPPORT     # Maven, Gradle support
```

**Available Agents:**

| Agent | Purpose | Best For |
|-------|---------|----------|
| `renovate` | JDK version management | Patch-level upgrades (e.g., 11.0.18 → 11.0.22) |
| `openrewrite` | Recipe-based code transformation | Major version migrations (e.g., 8 → 11, 11 → 17) |

### 2. Renovate Agent

Handles JDK patch-level version management:

```
┌─────────────────────────────────────────────────────────────────┐
│                       Renovate Agent                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Actions:                                                        │
│  ├── detect_version        Detect JDK from build files          │
│  ├── get_available_patches Query Adoptium for newer patches     │
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

### 3. OpenRewrite Agent

Handles major version migrations and code transformations:

```
┌─────────────────────────────────────────────────────────────────┐
│                     OpenRewrite Agent                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Actions:                                                        │
│  ├── list_recipes          List available migration recipes     │
│  ├── analyze_migration     Dry-run analysis of changes          │
│  ├── run_recipe            Execute transformation recipe        │
│  ├── suggest_migration_path Recommend upgrade steps             │
│  └── scan_security         OWASP Top 10 scanning                │
│                                                                  │
│  Available Recipes:                                              │
│  ├── java8to11            Java 8 → 11 migration                 │
│  ├── java11to17           Java 11 → 17 migration                │
│  ├── java17to21           Java 17 → 21 migration                │
│  ├── jakarta_ee9          javax.* → jakarta.* namespace         │
│  ├── spring_boot_3        Spring Boot 2.x → 3.0                 │
│  ├── junit5               JUnit 4 → 5 migration                 │
│  └── security_fixes       OWASP security fixes                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4. FastMCP Server

The MCP server uses **FastMCP** for clean, decorator-based tool definitions:

```python
from fastmcp import FastMCP

mcp = FastMCP(name="java-patching", version="1.0.0")

@mcp.tool()
async def detect_jdk_version(repository_path: str) -> dict:
    """Detect JDK version from build files."""
    result = await agent_registry.execute("renovate", "detect_version", ...)
    return result.to_dict()
```

**MCP Capabilities:**

| Type | Name | Description |
|------|------|-------------|
| Tool | `detect_jdk_version` | Detect JDK from build files |
| Tool | `get_available_patches` | Find newer patch versions |
| Tool | `preview_version_bump` | Preview version bump changes |
| Tool | `apply_version_bump` | Apply version bump |
| Tool | `list_migration_recipes` | List OpenRewrite recipes |
| Tool | `analyze_migration` | Dry-run migration analysis |
| Tool | `run_migration_recipe` | Execute transformation |
| Tool | `suggest_migration_path` | Plan upgrade path |
| Tool | `scan_security_vulnerabilities` | Security scanning |
| Resource | `jdk://versions/lts` | LTS version information |
| Resource | `agents://list` | Available agents |
| Prompt | `analyze-upgrade` | Guided upgrade workflow |
| Prompt | `migration-plan` | Migration planning workflow |
| Prompt | `security-audit` | Security audit workflow |

**Configuration for Claude Code:**
```json
// mcp-config.json
{
  "mcpServers": {
    "java-patching": {
      "command": "python",
      "args": ["backend/mcp_server.py"],
      "cwd": "${workspaceFolder}",
      "env": {
        "PYTHONPATH": "${workspaceFolder}/backend"
      }
    }
  }
}
```

### 5. Multi-LLM Service

Unified interface with **Gemini as the default** provider:

```python
LLMService
├── GeminiProvider      # Default - Gemini 1.5 Pro (cost-efficient)
├── OpenAIProvider      # GPT-4, GPT-4 Turbo
├── AnthropicProvider   # Claude 3.5 Sonnet, Claude 3 Opus
└── OllamaProvider      # Self-hosted (Llama 3, Mistral, etc.)
```

**LLM Use Cases:**
- Code impact analysis with suggestions
- Migration plan generation
- Explaining JDK changes
- Suggesting code fixes

## Data Flow

### Patch Upgrade Workflow (Renovate Agent)

```
1. DETECT                     2. DISCOVER                 3. ANALYZE
┌──────────────────┐         ┌──────────────────┐        ┌──────────────────┐
│ renovate:        │         │ renovate:        │        │ analyze_         │
│ detect_version   │  ───►   │ get_available_   │  ───►  │ repository       │
│                  │         │ patches          │        │                  │
│ Read build files │         │ Query Adoptium   │        │ Parse AST        │
│ Parse version    │         │ Compare versions │        │ Match changes    │
└──────────────────┘         └──────────────────┘        │ Score risk       │
                                                         └──────────────────┘
                                                                  │
4. BUMP                       5. REVIEW                           │
┌──────────────────┐         ┌──────────────────┐                │
│ renovate:        │  ◄───   │ renovate:        │   ◄────────────┘
│ apply_version_   │         │ preview_version_ │
│ bump             │         │ bump             │
│                  │         │                  │
│ Update files     │         │ Show diffs       │
│ Commit ready     │         │ Confirm changes  │
└──────────────────┘         └──────────────────┘
```

### Major Version Migration (OpenRewrite Agent)

```
1. SUGGEST PATH               2. ANALYZE                  3. EXECUTE
┌──────────────────┐         ┌──────────────────┐        ┌──────────────────┐
│ openrewrite:     │         │ openrewrite:     │        │ openrewrite:     │
│ suggest_         │  ───►   │ analyze_         │  ───►  │ run_recipe       │
│ migration_path   │         │ migration        │        │                  │
│                  │         │                  │        │ (dry_run=false)  │
│ 8→11→17 steps    │         │ Dry-run preview  │        │ Apply transforms │
└──────────────────┘         └──────────────────┘        └──────────────────┘
```

## API Structure

```
/api
├── /auth
│   ├── POST /register
│   ├── POST /login
│   ├── POST /ssh/challenge
│   ├── POST /ssh/verify
│   ├── GET  /me
│   └── PATCH /me
│
├── /repositories
│   ├── GET    /
│   ├── POST   /
│   ├── GET    /{id}
│   ├── PATCH  /{id}
│   ├── DELETE /{id}
│   ├── POST   /{id}/clone
│   └── POST   /{id}/pull
│
├── /automation
│   ├── GET  /{id}/jdk-version
│   ├── GET  /{id}/available-patches
│   ├── POST /{id}/preview-bump
│   ├── POST /{id}/apply-bump
│   └── POST /{id}/generate-renovate-config
│
├── /impact
│   ├── POST /analyze
│   ├── GET  /analyses
│   └── GET  /analyses/{id}
│
├── /skills
│   ├── GET  /
│   ├── GET  /categories
│   ├── GET  /tools
│   ├── GET  /{name}
│   └── POST /execute
│
├── /agent
│   ├── GET  /providers
│   ├── POST /chat
│   └── POST /chat/stream
│
├── /audit
│   ├── GET /logs
│   ├── GET /activity
│   └── GET /history
│
└── /patches
    ├── GET /changes
    ├── GET /versions
    └── GET /security-fixes
```

## Project Structure

```
JavaPatching/
├── backend/
│   ├── app/
│   │   ├── agents/                    # Multi-agent system
│   │   │   ├── base.py               # Agent base classes
│   │   │   ├── registry.py           # Agent registry
│   │   │   ├── renovate_agent.py     # Renovate agent
│   │   │   └── openrewrite_agent.py  # OpenRewrite agent
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── auth.py
│   │   │       ├── repositories.py
│   │   │       ├── automation.py
│   │   │       ├── impact.py
│   │   │       ├── skills.py
│   │   │       ├── agent.py
│   │   │       ├── audit.py
│   │   │       └── patches.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   └── security.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── renovate_service.py
│   │   │   ├── analyzer_service.py
│   │   │   ├── llm_service.py
│   │   │   └── ...
│   │   ├── skills/                   # Skill system (for REST API)
│   │   │   ├── base.py
│   │   │   ├── registry.py
│   │   │   └── *_skills.py
│   │   ├── mcp/                      # FastMCP server
│   │   │   └── server.py
│   │   └── main.py
│   ├── mcp_server.py                 # MCP entry point
│   ├── pyproject.toml
│   └── .env.example
│
├── frontend/
│   └── ...
│
├── docker-compose.yml
├── mcp-config.json
└── ARCHITECTURE.md
```

## Deployment

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
REDIS_URL=redis://host:6379

# Auth
SECRET_KEY=<random-secret>
JWT_ALGORITHM=HS256

# LLM Providers (Gemini is default, configure at least one)
GOOGLE_API_KEY=...              # Recommended
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_BASE_URL=http://localhost:11434

# Default provider
DEFAULT_LLM_PROVIDER=gemini     # Default
```

### Docker Compose

```yaml
services:
  frontend:     # React app on Nginx (port 3000)
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
    description = "Custom agent for specific tasks"
    version = "1.0.0"

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability.DEPENDENCY_ANALYSIS,
            AgentCapability.SECURITY_SCANNING,
        ]

    @property
    def actions(self) -> list[AgentAction]:
        return [
            AgentAction(
                name="my_action",
                description="Does something useful",
                parameters={...},
            ),
        ]

    async def execute(self, action: str, context: AgentContext, **kwargs) -> AgentResult:
        # Implementation
        ...
```

The agent is automatically:
- Registered in the agent registry
- Available via REST API
- Exposed via MCP tools (add to `server.py`)
- Usable by the orchestration layer

### Adding a New LLM Provider

```python
class MyProvider(LLMProvider):
    async def complete(self, messages: list[dict], **kwargs) -> str:
        ...

    async def stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        ...

# Register in LLMService._initialize_providers()
if settings.my_api_key:
    self.providers["my_provider"] = MyProvider(settings.my_api_key)
```

## Agent Orchestration

Agents can suggest next steps, enabling chained workflows:

```python
# Renovate agent might suggest OpenRewrite for major upgrades
result = AgentResult(
    success=False,
    agent_name="renovate",
    action="preview_version_bump",
    error="Major version change detected",
    suggested_next_agent="openrewrite",
    suggested_next_action="suggest_migration_path",
)
```

## Security Considerations

1. **Authentication**: JWT with short-lived access tokens, SSH key support
2. **Authorization**: User-scoped resources, ownership verification
3. **Audit Trail**: Complete logging of all actions
4. **Input Validation**: Pydantic schemas for all inputs
5. **SQL Injection**: SQLAlchemy ORM with parameterized queries
6. **MCP Security**: Runs locally, no network exposure by default

## Future Enhancements

1. **More Agents**: Dependency analysis, CI/CD integration
2. **GitHub/GitLab Integration**: Direct PR creation for version bumps
3. **Agent Collaboration**: Multi-agent workflows with handoffs
4. **Webhook Support**: Notify external systems of analysis results
5. **Team Features**: Multi-user workspaces, shared analyses
