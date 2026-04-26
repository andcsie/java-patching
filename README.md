# Java Patching Application

A multi-agent system for analyzing and managing JDK version upgrades in Java projects. Features automated patch discovery, AI-powered code analysis, fix generation, and PR creation.

## Features

- **Web UI**: React-based dashboard with 5-step upgrade workflow
- **Multi-Agent Architecture**: Specialized agents for different tasks
  - **Analysis Agent**: Impact analysis with AST parsing
  - **Fixer Agent**: AI-powered code fix generation
  - **Patcher Agent**: Patch creation, testing, and PR management
  - **Renovate Agent**: Patch-level JDK version management
  - **OpenRewrite Agent**: Major version migrations with recipes
  - **Orchestrator Agent**: Full automated upgrade pipeline
- **MCP Integration**: Works with Claude Code and Claude Desktop via FastMCP
- **Multi-LLM Support**: Gemini (default), OpenAI, Anthropic Claude, Ollama (self-hosted)
- **Git Integration**: SSH/HTTPS cloning, branch creation, push, and PR creation
- **Test Integration**: Run Maven/Gradle tests before creating PRs
- **Audit Trail**: Complete logging of all actions for compliance

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for frontend)
- **Docker** (for PostgreSQL)
- **Git**
- **Maven or Gradle** (for running Java tests)
- At least one LLM API key:
  - Google Gemini (recommended): https://makersuite.google.com/app/apikey
  - OpenAI: https://platform.openai.com/api-keys
  - Anthropic: https://console.anthropic.com/
  - Or Ollama for self-hosted: https://ollama.ai

**Optional (for automatic PR creation):**
- GitHub CLI (`gh`): `brew install gh && gh auth login`
- Or create PRs manually via the provided URL

## Quick Start

### TL;DR

```bash
# Clone and setup
git clone <repository-url>
cd JavaPatching

# Backend setup
python3 -m venv .venv
source .venv/bin/activate
cd backend
pip install -r requirements.txt

# Start database
cd ..
docker-compose -f docker-compose.dev.yml up -d

# Configure backend
cd backend
cp .env.example .env
# Edit .env and add GOOGLE_API_KEY (or another LLM provider key)
# Also set REPOS_BASE_PATH and REPOS_SCAN_PATH to your local paths

# Run migrations and create admin user
alembic upgrade head
python scripts/seed_admin.py

# Start backend server
uvicorn app.main:app --reload --port 8000

# In another terminal - Frontend setup
cd ../frontend
npm install
npm run dev
```

**URLs:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

**Default credentials:** `admin` / `admin`

## Installation

### 1. Clone and Install Backend

```bash
git clone <repository-url>
cd JavaPatching

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install backend dependencies
cd backend
pip install -r requirements.txt
```

### 2. Start PostgreSQL

```bash
cd ..  # Back to project root
docker-compose -f docker-compose.dev.yml up -d

# Verify it's running
docker-compose -f docker-compose.dev.yml ps
```

### 3. Configure Backend

```bash
cd backend
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# Required: At least one LLM provider
GOOGLE_API_KEY=your-gemini-api-key        # Recommended

# Required: Repository storage paths
REPOS_BASE_PATH=/path/to/JavaPatching/repos
REPOS_SCAN_PATH=/path/to/your/java/projects  # For auto-discovery

# Optional: Additional LLM providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_BASE_URL=http://localhost:11434
```

Create the repos directory:
```bash
mkdir -p /path/to/JavaPatching/repos
```

### 4. Initialize Database

```bash
cd backend
alembic upgrade head
python scripts/seed_admin.py
```

### 5. Start Backend

```bash
uvicorn app.main:app --reload --port 8000
```

### 6. Install and Start Frontend

```bash
cd ../frontend
npm install
npm run dev
```

The frontend will be available at http://localhost:5173

## Web UI Workflow

The web interface provides a 5-step upgrade workflow:

```
1. Analyze  →  2. Fix  →  3. Patch  →  4. Test  →  5. PR
```

### Step-by-Step Guide

1. **Add Repository**: Enter a Git URL (HTTPS or SSH) and clone it
2. **Set Versions**: Enter the current and target JDK versions (e.g., 11.0.18 → 11.0.22)
3. **Analyze**: Find compatibility issues between versions
4. **Fix**: Generate AI-powered code fixes for each issue
5. **Patch**: Create unified diff patches from the fixes
6. **Test**: Run Maven/Gradle tests to verify changes compile and pass
7. **PR**: Create a git branch, commit changes, push, and create a PR

### Options

- **Push**: Push the branch to the remote repository
- **Create PR**: Create a pull request (requires Push enabled)
  - If `gh` CLI is installed: Creates PR automatically
  - Otherwise: Provides a URL to create PR manually

## Configuration

### Environment Variables

Create `backend/.env`:

```bash
# Application
APP_NAME="Java Patching Application"
DEBUG=false

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/javapatching
REDIS_URL=redis://localhost:6379

# Authentication
SECRET_KEY=change-this-to-a-random-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=120

# LLM Providers (configure at least one)
GOOGLE_API_KEY=your-key-here          # Recommended
GOOGLE_MODEL=gemini-2.5-flash

OPENAI_API_KEY=                        # Optional
OPENAI_MODEL=gpt-4-turbo

ANTHROPIC_API_KEY=                     # Optional
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

OLLAMA_BASE_URL=http://localhost:11434 # Optional (self-hosted)
OLLAMA_MODEL=llama3

# Default LLM provider
DEFAULT_LLM_PROVIDER=gemini

# Repository storage
REPOS_BASE_PATH=/full/path/to/JavaPatching/repos
REPOS_SCAN_PATH=/full/path/to/your/projects
```

### Repository Cloning

The application supports both HTTPS and SSH Git URLs:

- **HTTPS**: `https://github.com/user/repo.git`
- **SSH**: `git@github.com:user/repo.git`

If you only have SSH keys configured, HTTPS URLs will be automatically converted to SSH format.

## Available Agents

### Analysis Agent

Analyzes JDK upgrade impacts using AST parsing.

| Action | Description |
|--------|-------------|
| `analyze_impact` | Full AST-based impact analysis |
| `explain_impacts` | Add LLM explanations to impacts |
| `get_release_notes` | Fetch JDK release notes |
| `get_security_advisories` | Get CVEs fixed between versions |

### Fixer Agent

Generates code fixes using LLM.

| Action | Description |
|--------|-------------|
| `generate_fixes` | Generate fixes for all impacts |
| `generate_single_fix` | Generate fix for one impact |
| `validate_fix` | Validate a generated fix |

### Patcher Agent

Creates patches and manages PRs.

| Action | Description |
|--------|-------------|
| `create_patches` | Create unified diffs from fixes |
| `apply_all_patches` | Apply patches to files |
| `run_tests` | Run Maven/Gradle tests |
| `create_pr` | Create branch, commit, push, and PR |

### Renovate Agent

Manages patch-level JDK versions.

| Action | Description |
|--------|-------------|
| `detect_version` | Detect JDK from build files |
| `get_available_patches` | Query Adoptium for updates |
| `preview_version_bump` | Preview version changes |
| `apply_version_bump` | Apply version bump |

### OpenRewrite Agent

Handles major version migrations.

| Action | Description |
|--------|-------------|
| `list_recipes` | List migration recipes |
| `analyze_migration` | Dry-run analysis |
| `run_recipe` | Execute transformation |
| `suggest_migration_path` | Plan upgrade path |

### Orchestrator Agent

Runs the full upgrade pipeline.

| Action | Description |
|--------|-------------|
| `full_upgrade` | Complete automated upgrade |

## API Reference

### Authentication

```bash
# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin"

# Response: {"access_token": "...", "token_type": "bearer"}
```

### Agents API

```bash
# List all agents
curl http://localhost:8000/api/agents

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
```

### Repositories API

```bash
# Create repository
curl -X POST http://localhost:8000/api/repositories \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-project", "url": "git@github.com:user/repo.git"}'

# Clone repository
curl -X POST http://localhost:8000/api/repositories/{id}/clone \
  -H "Authorization: Bearer $TOKEN"
```

## MCP Integration (Claude Code/Desktop)

### Automatic Setup

The `mcp-config.json` is pre-configured. Just restart Claude Code in this directory.

### Available MCP Tools

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

### Claude Desktop Configuration

Add to `~/.config/claude/claude_desktop_config.json`:

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
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

### Frontend Development

```bash
cd frontend
npm run dev      # Development server with hot reload
npm run build    # Production build
npm run preview  # Preview production build
```

## Troubleshooting

### Clone fails with SSH error

If you only have SSH keys configured:
- The application automatically converts HTTPS URLs to SSH format
- Make sure your SSH key is added to the ssh-agent: `ssh-add ~/.ssh/id_rsa`

### Tests fail with "mvn not found"

Install Maven:
```bash
brew install maven  # macOS
```

### PR not created automatically

Install GitHub CLI:
```bash
brew install gh
gh auth login
```

Or use the manual PR URL provided in the response.

### Frontend can't connect to backend

Check that the backend is running on port 8000 and CORS is configured.

### LLM errors

Verify your API key is set correctly in `.env` and the provider is available:
```bash
curl http://localhost:8000/api/agents/llm/providers
```

## Project Structure

```
JavaPatching/
├── backend/
│   ├── app/
│   │   ├── agents/           # Multi-agent system
│   │   │   ├── analysis_agent.py
│   │   │   ├── fixer_agent.py
│   │   │   ├── patcher_agent.py
│   │   │   ├── renovate_agent.py
│   │   │   ├── openrewrite_agent.py
│   │   │   └── orchestrator_agent.py
│   │   ├── api/routes/       # REST API endpoints
│   │   ├── core/             # Config, database, security
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   └── mcp/              # FastMCP server
│   ├── alembic/              # Database migrations
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── hooks/            # Custom hooks
│   │   ├── services/         # API client
│   │   └── App.tsx
│   └── package.json
├── docker-compose.yml        # Full stack
├── docker-compose.dev.yml    # Development (DB only)
├── mcp-config.json           # Claude Code config
└── README.md
```

## License

MIT
