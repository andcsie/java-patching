# Multi-Agent Architecture

## Overview

The JavaPatching backend uses a multi-agent architecture where specialized agents communicate via a central message bus. Each agent has a single responsibility and can be orchestrated into workflows.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        OrchestratorAgent                            │
│                   (Coordinates Full Workflows)                       │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         AgentBus                                     │
│              (Pub/Sub Messaging + Event System)                      │
└─────┬─────────┬─────────┬─────────┬─────────┬───────────────────────┘
      │         │         │         │         │
      ▼         ▼         ▼         ▼         ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ Scanner │ │ Release │ │ Analysis│ │  Fixer  │ │ Patcher │
│  Agent  │ │  Notes  │ │  Agent  │ │  Agent  │ │  Agent  │
│         │ │  Agent  │ │ (+LLM)  │ │  (LLM)  │ │  (LLM)  │
└─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘
                              │
                              │ Analysis includes
                              │ LLM explanations
                              ▼
                    ┌─────────────────┐
                    │  Impact Agent   │
                    │ (Code Scanning) │
                    └─────────────────┘
      │                                         │
      │                                         │
      ▼                                         ▼
┌─────────────────┐                   ┌─────────────────┐
│ RenovateAgent   │                   │ OpenRewriteAgent│
│ (Patch Upgrades)│                   │ (Major Upgrades)│
│ Adoptium API    │                   │ Dynamic Recipes │
└─────────────────┘                   └─────────────────┘
```

## Agent Responsibilities

### AnalysisAgent (includes LLM)
**Purpose:** Analyze JDK upgrade impacts WITH LLM-powered explanations

| Action | Description | LLM |
|--------|-------------|-----|
| `analyze_impact` | Scan code + explain impacts | ✅ Yes (parallel) |
| `analyze_impact` (skip_llm=true) | Fast scan without explanations | ❌ No |
| `get_release_notes` | Fetch JDK release notes | ❌ No |
| `get_security_advisories` | Get CVEs between versions | ❌ No |
| `suggest_upgrade_path` | Plan upgrade steps | ❌ No |

**Output:** List of impacts with `llm_explanation` field for each

### FixerAgent (separate, LLM)
**Purpose:** Generate code fixes for impacts

| Action | Description |
|--------|-------------|
| `generate_fixes` | LLM generates fix for each impact |
| `fix_single` | Fix a single impact |
| `validate_fix` | Validate generated fix |

**Input:** Impacts from AnalysisAgent
**Output:** Impacts with `fix` field containing suggested code

### PatcherAgent (separate, LLM)
**Purpose:** Create unified diff patches

| Action | Description |
|--------|-------------|
| `create_patches` | Generate patches for all files |
| `create_single_patch` | Patch for one file |
| `apply_patch` | Apply patch to file |
| `validate_patch` | Validate patch syntax |

**Input:** Impacts with fixes from FixerAgent
**Output:** Unified diff patches per file

### OrchestratorAgent
**Purpose:** Coordinate multi-agent workflows

| Action | Description |
|--------|-------------|
| `full_upgrade` | Run complete pipeline |
| `quick_scan` | Fast impact assessment |
| `patch_upgrade` | Simple version bump |
| `major_upgrade` | OpenRewrite migration |

### RenovateAgent
**Purpose:** JDK version management (patch upgrades)

- Uses **Adoptium API** for patch discovery
- Detects JDK from build files
- Self-contained Python implementation (no external tools)

### OpenRewriteAgent
**Purpose:** Recipe-based code transformations (major upgrades)

- **Dynamically fetches recipes** from Moderne API / OpenRewrite docs
- Falls back to known recipes if APIs unavailable
- Requires Maven/Gradle with OpenRewrite plugin

## User Workflow

### UI Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        Quick Actions                             │
├─────────────┬─────────────┬─────────────┬───────────┬───────────┤
│   Detect    │    Get      │  Analyze    │   Quick   │  Security │
│   Version   │   Patches   │   Impact    │   Scan    │   CVEs    │
│  (renovate) │ (renovate)  │ (analysis)  │(analysis) │ (analysis)│
│             │             │  + LLM ✨   │  no LLM   │           │
└─────────────┴─────────────┴──────┬──────┴───────────┴───────────┘
                                   │
                                   │ Returns impacts with
                                   │ LLM explanations
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Code Transformation                            │
├───────────────────┬───────────────────┬─────────────────────────┤
│   Generate Fixes  │   Create Patches  │     Full Upgrade        │
│   (fixer agent)   │  (patcher agent)  │   (orchestrator)        │
│      LLM ✨       │      LLM ✨        │   All agents ✨          │
└───────────────────┴───────────────────┴─────────────────────────┘
```

### Step-by-Step Workflow

1. **Analyze Impact** (with LLM)
   - Agent: `analysis`
   - Action: `analyze_impact`
   - Scans code for JDK upgrade impacts
   - LLM explains each impact (parallel, 5 concurrent)
   - Returns: `impacts[]` with `llm_explanation`

2. **Generate Fixes** (separate call)
   - Agent: `fixer`
   - Action: `generate_fixes`
   - Input: `impacts` from step 1
   - LLM generates code fix for each impact
   - Returns: `impacts_with_fixes[]` with `fix` field

3. **Create Patches** (separate call)
   - Agent: `patcher`
   - Action: `create_patches`
   - Input: `impacts_with_fixes` from step 2
   - LLM creates unified diffs
   - Returns: `patches[]` per file

### Alternative: Fast Mode

For quick scans without LLM overhead:

```
analysis:analyze_impact { skip_llm: true }
```

Returns impacts without explanations (faster).

### Alternative: Full Orchestration

Run all agents automatically:

```
orchestrator:full_upgrade {
  repository_path: "/path/to/repo",
  from_version: "11.0.18",
  to_version: "11.0.22"
}
```

Orchestrator runs: Scanner → ReleaseNotes → Impact → Explainer → Fixer → Patcher → Renovate

## API Endpoints

### Execute Agent Action

```http
POST /api/agents/{agent_name}/actions/{action_name}
Content-Type: application/json

{
  "repository_id": "uuid",
  "parameters": {
    "repository_path": "/path/to/repo",
    "from_version": "11.0.18",
    "to_version": "11.0.22",
    "llm_provider": "anthropic",
    "skip_llm": false
  }
}
```

### Response

```json
{
  "success": true,
  "agent_name": "analysis",
  "action": "analyze_impact",
  "data": {
    "risk_score": 45,
    "risk_level": "medium",
    "total_impacts": 3,
    "impacts": [
      {
        "file_path": "/path/to/File.java",
        "line_number": 42,
        "code_snippet": "SecurityManager sm = ...",
        "change_type": "deprecated",
        "severity": "high",
        "description": "SecurityManager deprecated in JDK 17",
        "llm_explanation": {
          "summary": "This code uses SecurityManager which is deprecated...",
          "risk": "Runtime warnings, future removal",
          "recommendation": "Migrate to Security Manager alternatives"
        }
      }
    ]
  },
  "suggested_next_agent": "fixer",
  "suggested_next_action": "generate_fixes"
}
```

## Agent Communication

### AgentBus

Pub/Sub messaging for inter-agent communication:

```python
# Subscribe to events
agent_bus.subscribe("analysis.complete", handler)
agent_bus.subscribe("fixer.*", handler)  # All fixer events

# Publish events
await agent_bus.publish(AgentMessage(
    type=MessageType.EVENT,
    from_agent="analysis",
    action="complete",
    payload={"impacts": [...]},
))
```

### WorkflowContext (Blackboard Pattern)

Shared state for orchestrated workflows:

```python
@dataclass
class WorkflowContext:
    workflow_id: UUID
    repository_path: str
    from_version: str
    to_version: str

    # Results from each stage
    scan_result: dict | None
    release_notes: list[dict]
    impacts: list[dict]          # From AnalysisAgent
    explanations: list[dict]     # LLM explanations (included in impacts)
    fixes: list[dict]            # From FixerAgent
    patches: list[dict]          # From PatcherAgent
    version_bumps: list[dict]    # From RenovateAgent

    # Metadata
    risk_score: int
    risk_level: str
    completed_stages: list[str]
```

## Performance Optimizations

### Parallel LLM Calls

All LLM operations run with concurrency limit:

```python
semaphore = asyncio.Semaphore(10)  # Max 10 concurrent

async def explain_one(impact, index):
    async with semaphore:
        return await llm_service.explain_impact(...)

tasks = [explain_one(impact, i) for i, impact in enumerate(impacts)]
results = await asyncio.gather(*tasks)
```

### Release Notes Fetching

- Fetches all versions in parallel
- Oracle + Adoptium fetched in parallel per version
- 3-second timeout (fail fast)
- Results cached per version

### File Content Caching

FixerAgent caches file contents to avoid re-reading:

```python
file_cache: dict[str, str | None] = {}
def get_file_content(path):
    if path not in file_cache:
        file_cache[path] = Path(path).read_text()
    return file_cache[path]
```

## OpenRewrite Recipe Fetching

Recipes are fetched dynamically (not hardcoded):

1. **Moderne API** - Primary source
2. **OpenRewrite Docs** - Fallback
3. **Known Recipes** - Final fallback

```python
# Search for recipes
recipes = await recipe_service.search_recipes("java 17")

# Get specific recipe
recipe = await recipe_service.get_recipe(
    "org.openrewrite.java.migrate.UpgradeToJava17"
)
```

## Adding New Agents

1. Create agent file in `app/agents/`:

```python
from app.agents.base import Agent, AgentAction, AgentCapability
from app.agents.registry import register_agent

@register_agent
class MyAgent(Agent):
    name = "my_agent"
    description = "Does something useful"
    version = "1.0.0"

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [AgentCapability.IMPACT_ANALYSIS]

    @property
    def actions(self) -> list[AgentAction]:
        return [
            AgentAction(
                name="my_action",
                description="Performs my action",
                parameters={...},
            ),
        ]

    async def execute(self, action: str, context: AgentContext, **kwargs) -> AgentResult:
        if action == "my_action":
            return await self._my_action(context, **kwargs)
        ...
```

2. Import in `app/agents/__init__.py`:

```python
from app.agents import my_agent  # noqa: F401
```

3. Agent is automatically registered and available via API.

## Summary

| Agent | Responsibility | Uses LLM |
|-------|---------------|----------|
| **analysis** | Impact detection + explanations | ✅ Yes |
| **fixer** | Code fix generation | ✅ Yes |
| **patcher** | Unified diff creation | ✅ Yes |
| **orchestrator** | Workflow coordination | ❌ No |
| **renovate** | Version bumping | ❌ No |
| **openrewrite** | Recipe execution | ❌ No |
| **scanner** | File scanning | ❌ No |
| **release_notes** | Release notes fetching | ❌ No |
| **impact** | Code impact analysis | ❌ No |
| **explainer** | Impact explanations | ✅ Yes |

**Key Design Decisions:**
- Analysis includes LLM explanations (single call for analyze + explain)
- Fixing is a **separate agent** (user must explicitly request)
- Patching is a **separate agent** (user must explicitly request)
- All LLM calls run in parallel (5 concurrent max)
- OpenRewrite recipes fetched dynamically from APIs
