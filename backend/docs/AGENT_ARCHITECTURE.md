# Multi-Agent Architecture

## Overview

The JavaPatching backend uses a multi-agent architecture where specialized agents communicate via a central message bus. Each agent has a single responsibility and can be orchestrated into workflows.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        OrchestratorAgent                            │
│                   (Coordinates Workflows)                           │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         AgentBus                                     │
│              (Pub/Sub Messaging + Event System)                      │
└─────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────────┘
      │         │         │         │         │         │
      ▼         ▼         ▼         ▼         ▼         ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ Scanner │ │ Release │ │ Impact  │ │Explainer│ │  Fixer  │ │ Patcher │
│  Agent  │ │  Notes  │ │  Agent  │ │  Agent  │ │  Agent  │ │  Agent  │
│         │ │  Agent  │ │         │ │  (LLM)  │ │  (LLM)  │ │  (LLM)  │
└─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘
      │                       │
      │                       │
      ▼                       ▼
┌─────────────────┐   ┌─────────────────┐
│ RenovateAgent   │   │ OpenRewriteAgent│
│ (Patch Upgrades)│   │ (Major Upgrades)│
└─────────────────┘   └─────────────────┘
```

## Agents

### Core Pipeline Agents

| Agent | Responsibility | Input | Output |
|-------|---------------|-------|--------|
| **ScannerAgent** | Scan repository for Java files | Repository path | List of Java files, build tool info |
| **ReleaseNotesAgent** | Fetch JDK release notes | Version range | List of changes (deprecated, removed, security) |
| **ImpactAgent** | Analyze code against changes | Files + Changes | List of impacts with risk scores |
| **ExplainerAgent** | LLM-powered explanations | Impacts | Explained impacts with context |
| **FixerAgent** | LLM-powered fix generation | Impacts | Impacts with suggested fixes |
| **PatcherAgent** | Create unified diffs | Fixes | Patch files |

### Tool Agents

| Agent | Responsibility | Use Case |
|-------|---------------|----------|
| **RenovateAgent** | Version bumping via Adoptium API | Patch upgrades (11.0.18 → 11.0.22) |
| **OpenRewriteAgent** | Recipe-based code transformations | Major upgrades (11 → 17) |

### Orchestration

| Agent | Responsibility |
|-------|---------------|
| **OrchestratorAgent** | Coordinates multi-agent workflows, manages state |

## Communication Patterns

### AgentBus (Current Implementation)

The `AgentBus` provides:

1. **Pub/Sub Messaging**: Agents publish events, others subscribe
2. **Request/Response**: Synchronous agent-to-agent calls
3. **Event Patterns**: Wildcard subscriptions (`scanner.*`, `*`)

```python
# Subscribe to events
agent_bus.subscribe("scanner.complete", handler)
agent_bus.subscribe("impact.*", handler)  # All impact events
agent_bus.subscribe("*", logger)  # All events

# Publish events
await agent_bus.publish(AgentMessage(
    type=MessageType.EVENT,
    from_agent="scanner",
    action="complete",
    payload={"files": [...]},
))

# Request/Response
response = await agent_bus.request(
    from_agent="orchestrator",
    to_agent="impact",
    action="analyze",
    payload={"repository_path": "/path/to/repo"},
)
```

### WorkflowContext (Blackboard Pattern)

Shared state for workflow execution:

```python
@dataclass
class WorkflowContext:
    workflow_id: UUID
    repository_path: str
    from_version: str
    to_version: str

    # Results from each stage
    scan_result: dict | None = None
    release_notes: list[dict] = field(default_factory=list)
    impacts: list[dict] = field(default_factory=list)
    explanations: list[dict] = field(default_factory=list)
    fixes: list[dict] = field(default_factory=list)
    patches: list[dict] = field(default_factory=list)

    # Metadata
    risk_score: int = 0
    risk_level: str = "unknown"
    completed_stages: list[str] = field(default_factory=list)
```

## Workflows

### Full Upgrade Pipeline

```
1. Scanner       → Scan Java files
2. ReleaseNotes  → Fetch changes between versions
3. Impact        → Analyze code against changes
4. Explainer     → LLM explains each impact
5. Fixer         → LLM generates fixes
6. Patcher       → Create unified diff patches
7. Renovate      → (Optional) Version bump
```

### Quick Scan

```
1. Impact → Analyze code (no LLM)
```

### Patch Upgrade

```
1. Renovate → Preview/apply version bump
```

### Major Upgrade

```
1. OpenRewrite → Suggest migration path
2. OpenRewrite → Run recipes (dry-run or apply)
```

## Alternative: A2A Protocol

### What is A2A?

A2A (Agent-to-Agent) is Google's open protocol for agent interoperability:
- **Transport**: HTTP/JSON-RPC 2.0
- **Discovery**: Agent Cards (`/.well-known/agent.json`)
- **State**: Task objects with artifacts
- **Streaming**: SSE for long-running tasks

### Comparison

| Feature | AgentBus (Current) | A2A Protocol |
|---------|-------------------|--------------|
| Transport | In-process async | HTTP/JSON-RPC |
| Discovery | Registry | Agent Cards |
| State | Shared WorkflowContext | Task objects |
| Streaming | Pub/Sub events | SSE |
| External Agents | No | Yes |
| Latency | ~0ms (in-process) | Network latency |
| Deployment | Single process | Distributed |

### When to Use A2A

- Integrate **external agents** (other services/APIs)
- Agents run as **separate microservices**
- Need **vendor-neutral** agent interop
- Multi-language agent systems

### When to Use AgentBus

- All agents run **in-process**
- Single deployment
- Lower latency requirements
- Tighter codebase integration

## API Endpoints

### Execute Agent Action

```http
POST /api/agents/{agent_name}/actions/{action_name}
Content-Type: application/json

{
  "parameters": {
    "repository_path": "/path/to/repo",
    "from_version": "11.0.18",
    "to_version": "11.0.22"
  }
}
```

### List Agents

```http
GET /api/agents
```

### Get Agent Actions

```http
GET /api/agents/{agent_name}/actions
```

## Usage Examples

### Full Analysis via Orchestrator

```python
from app.agents import agent_registry
from app.agents.base import AgentContext

context = AgentContext(user_id=user.id)

result = await agent_registry.execute(
    "orchestrator",
    "full_upgrade",
    context,
    repository_path="/path/to/repo",
    from_version="11.0.18",
    to_version="11.0.22",
    llm_provider="anthropic",
)

print(result.data["risk_score"])
print(result.data["patches"])
```

### Direct Agent Call

```python
result = await agent_registry.execute(
    "impact",
    "analyze",
    context,
    repository_path="/path/to/repo",
    from_version="11.0.18",
    to_version="11.0.22",
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

## Renovate Integration

The `RenovateAgent` is a **self-contained Python implementation** that:
- Uses **Adoptium API** for patch discovery
- Detects JDK version from `pom.xml`, `build.gradle`, `.java-version`, etc.
- Generates and applies version bumps

No external Renovate installation required.

## OpenRewrite Integration

The `OpenRewriteAgent` provides:
- Predefined recipes for JDK migrations (8→11, 11→17, 17→21)
- Security fixes (OWASP Top 10)
- Spring Boot migrations

**Note**: Actual recipe execution requires Maven/Gradle with OpenRewrite plugin installed in the target repository.
