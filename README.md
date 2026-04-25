# Java Patching Application

A multi-agent system for analyzing and managing JDK version upgrades in Java projects. Features automated patch discovery, major version migration planning, and AI-powered code analysis.

## Features

- **Multi-Agent Architecture**: Specialized agents for different tasks
  - **Renovate Agent**: Patch-level JDK version management (e.g., 11.0.18 → 11.0.22)
  - **OpenRewrite Agent**: Major version migrations with recipe-based code transformation
- **MCP Integration**: Works with Claude Code and Claude Desktop via FastMCP
- **Multi-LLM Support**: Gemini (default), OpenAI, Anthropic Claude, Ollama (self-hosted)
- **Code Analysis**: AST-based impact analysis using tree-sitter
- **Audit Trail**: Complete logging of all actions for compliance

## Prerequisites

- **Python 3.11+**
- **Docker** (for PostgreSQL)
- **Git**
- At least one LLM API key:
  - Google Gemini (recommended): https://makersuite.google.com/app/apikey
  - OpenAI: https://platform.openai.com/api-keys
  - Anthropic: https://console.anthropic.com/
  - Or Ollama for self-hosted: https://ollama.ai

## Quick Start

### TL;DR

```bash
# Clone and setup
git clone <repository-url>
cd JavaPatching
python3 -m venv .venv
source .venv/bin/activate
cd backend
pip install -r requirements.txt

# Start database
cd ..
docker-compose -f docker-compose.dev.yml up -d

# Configure
cd backend
cp .env.example .env
# Edit .env and add GOOGLE_API_KEY (or another LLM provider key)

# Run migrations and create admin user
alembic upgrade head
python scripts/seed_admin.py

# Start server
uvicorn app.main:app --reload
```

**Default credentials:** `admin` / `admin`

### 1. Clone and Install Dependencies

```bash
# Clone the repository
git clone <repository-url>
cd JavaPatching

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Verify installation
python -c "from app.agents import agent_registry; print('OK')"
```

### 2. Start PostgreSQL

```bash
cd ..  # Back to project root
docker-compose -f docker-compose.dev.yml up -d

# Verify it's running
docker-compose -f docker-compose.dev.yml ps
```

### 3. Configure and Run Backend

```bash
cd backend

# Create environment file
cp .env.example .env

# Edit .env and add your API key
# At minimum, set one of: GOOGLE_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY
nano .env  # or use your preferred editor

# Run database migrations
alembic upgrade head

# Create default admin user
python scripts/seed_admin.py

# Start the API server
uvicorn app.main:app --reload
```

The API is now running at http://localhost:8000

**Default login:** `admin` / `admin`

### 4. Use with Claude Code (MCP)

The MCP server is already configured. Restart Claude Code in this directory and the tools will be available:

```
detect_jdk_version
get_available_patches
preview_version_bump
apply_version_bump
list_migration_recipes
analyze_migration
run_migration_recipe
suggest_migration_path
scan_security_vulnerabilities
```

## Services

### PostgreSQL Database

```bash
# Start
docker-compose -f docker-compose.dev.yml up -d

# Stop
docker-compose -f docker-compose.dev.yml down

# View logs
docker-compose -f docker-compose.dev.yml logs -f db

# Reset database (removes all data)
docker-compose -f docker-compose.dev.yml down -v
```

### Backend API (FastAPI)

```bash
cd backend

# Development mode (with auto-reload)
uvicorn app.main:app --reload --port 8000

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Endpoints:**
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- OpenAPI: http://localhost:8000/openapi.json

### MCP Server (for Claude Code/Desktop)

**Option A: Automatic (via mcp-config.json)**

Already configured - just restart Claude Code in this directory.

**Option B: Manual**

```bash
cd backend
python mcp_server.py
```

**Option C: Using uvx**

```bash
uvx fastmcp run backend/app/mcp/server.py:mcp
```

### Redis (Optional)

Uncomment the redis service in `docker-compose.dev.yml`, then:

```bash
docker-compose -f docker-compose.dev.yml up -d
```

### Full Stack (Docker Compose)

For production-like deployment with all services:

```bash
docker-compose up -d
```

This starts: Frontend (3000), Backend (8000), PostgreSQL (5432), Redis (6379)

## Configuration

### Environment Variables

Create `backend/.env` from the example:

```bash
cp backend/.env.example backend/.env
```

**Required:**
```bash
# At least one LLM provider
GOOGLE_API_KEY=your-gemini-api-key        # Recommended (default)
# Or
OPENAI_API_KEY=sk-...
# Or
ANTHROPIC_API_KEY=sk-ant-...
# Or
OLLAMA_BASE_URL=http://localhost:11434    # Self-hosted
```

**Optional:**
```bash
# Database (defaults work with docker-compose.dev.yml)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/javapatching
REDIS_URL=redis://localhost:6379

# Auth
SECRET_KEY=change-this-to-a-random-secret-key

# LLM preference
DEFAULT_LLM_PROVIDER=gemini   # gemini, openai, anthropic, ollama
```

### MCP Configuration

The `mcp-config.json` in the project root configures Claude Code:

```json
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

For Claude Desktop, add to `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "java-patching": {
      "command": "python",
      "args": ["/full/path/to/JavaPatching/backend/mcp_server.py"],
      "env": {
        "PYTHONPATH": "/full/path/to/JavaPatching/backend"
      }
    }
  }
}
```

## Available Agents

### Analysis Agent

Best for: Understanding upgrade impact before making changes

| Action | Description |
|--------|-------------|
| `get_release_notes` | Fetch JDK release notes between versions |
| `analyze_impact` | Full AST-based impact analysis against release notes |
| `get_security_advisories` | Get CVEs fixed between versions |
| `suggest_upgrade_path` | Recommend upgrade strategy (patch vs major) |

**How it works:**
1. Fetches changes from OpenJDK/Adoptium release notes
2. Parses Java files using tree-sitter AST
3. Matches code usage against deprecated/removed APIs
4. Calculates risk score and severity
5. Uses LLM to generate migration suggestions

### Renovate Agent

Best for: Patch-level upgrades within the same major version

| Action | Description |
|--------|-------------|
| `detect_version` | Detect JDK version from pom.xml, build.gradle, .java-version, etc. |
| `get_available_patches` | Query Adoptium API for newer patch versions |
| `preview_version_bump` | Show diffs before applying changes |
| `apply_version_bump` | Update version in build files |
| `generate_config` | Create renovate.json for automated updates |

### OpenRewrite Agent

Best for: Major version migrations (8→11, 11→17, 17→21)

| Action | Description |
|--------|-------------|
| `list_recipes` | List available migration recipes |
| `analyze_migration` | Dry-run analysis of what would change |
| `run_recipe` | Execute a transformation recipe |
| `suggest_migration_path` | Recommend step-by-step upgrade path |
| `scan_security` | OWASP Top 10 vulnerability scanning |

**Available Recipes:**
- `java8to11` - Java 8 → 11 migration
- `java11to17` - Java 11 → 17 migration
- `java17to21` - Java 17 → 21 migration
- `jakarta_ee9` - javax.* → jakarta.* namespace
- `spring_boot_3` - Spring Boot 2.x → 3.0
- `junit5` - JUnit 4 → 5 migration
- `security_fixes` - OWASP security fixes

## Agents API

All agents can be invoked via the REST API:

```bash
# List all agents
curl http://localhost:8000/api/agents

# Get agent details
curl http://localhost:8000/api/agents/analysis

# List agent actions
curl http://localhost:8000/api/agents/analysis/actions

# Execute an action
curl -X POST http://localhost:8000/api/agents/analysis/execute/analyze_impact \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "repository_id": "uuid-here",
    "parameters": {
      "from_version": "11.0.18",
      "to_version": "11.0.22"
    }
  }'

# Health check all agents
curl http://localhost:8000/api/agents/health

# Get LLM tool definitions (for function calling)
curl http://localhost:8000/api/agents/tools
```

### Automation API (Renovate-style shortcuts)

```bash
# Detect JDK version
curl http://localhost:8000/api/automation/{repo_id}/jdk-version

# Get available patches
curl http://localhost:8000/api/automation/{repo_id}/available-patches

# Preview version bump
curl -X POST http://localhost:8000/api/automation/{repo_id}/preview-bump \
  -d '{"target_version": "11.0.22"}'

# Apply version bump
curl -X POST http://localhost:8000/api/automation/{repo_id}/apply-bump \
  -d '{"target_version": "11.0.22"}'
```

## Development

### Running Tests

```bash
cd backend
pip install -e ".[dev]"
pytest
```

### Code Formatting

```bash
cd backend
ruff check --fix .
ruff format .
```

### Database Migrations

```bash
cd backend

# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

### Adding a New Agent

1. Create `backend/app/agents/my_agent.py`:

```python
from app.agents.base import Agent, AgentAction, AgentCapability
from app.agents.registry import register_agent

@register_agent
class MyAgent(Agent):
    name = "my_agent"
    description = "Does something useful"

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [AgentCapability.IMPACT_ANALYSIS]

    @property
    def actions(self) -> list[AgentAction]:
        return [
            AgentAction(
                name="my_action",
                description="Performs analysis",
                parameters={"type": "object", "properties": {...}},
            ),
        ]

    async def execute(self, action, context, **kwargs):
        # Implementation
        ...
```

2. Import in `backend/app/agents/__init__.py`
3. Add MCP tools in `backend/app/mcp/server.py`

## Project Structure

```
JavaPatching/
├── backend/
│   ├── app/
│   │   ├── agents/          # Multi-agent system
│   │   ├── api/routes/      # REST API endpoints
│   │   ├── core/            # Config, database, security
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # Business logic
│   │   ├── skills/          # Skill system
│   │   └── mcp/             # FastMCP server
│   ├── alembic/             # Database migrations
│   ├── mcp_server.py        # MCP entry point
│   └── pyproject.toml
├── frontend/                 # React frontend
├── docker-compose.yml        # Full stack deployment
├── docker-compose.dev.yml    # Development (DB only)
├── mcp-config.json          # Claude Code MCP config
└── ARCHITECTURE.md          # Detailed architecture docs
```

## Troubleshooting

### MCP tools not appearing in Claude Code

1. Ensure you're in the JavaPatching directory
2. Check that `mcp-config.json` exists
3. Restart Claude Code
4. Verify Python path: `which python`

### Database connection errors

```bash
# Check if PostgreSQL is running
docker-compose -f docker-compose.dev.yml ps

# Check logs
docker-compose -f docker-compose.dev.yml logs db
```

### Alembic migration errors

```bash
# Check current revision
alembic current

# Reset to clean state (loses data)
docker-compose -f docker-compose.dev.yml down -v
docker-compose -f docker-compose.dev.yml up -d
alembic upgrade head
```

## License

MIT
