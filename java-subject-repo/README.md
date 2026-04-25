# Java Subject Repository

Sample Java project for testing JDK upgrade impact analysis.

## Current Version

- **JDK**: 11.0.18
- **Target**: 11.0.22 (patch) or 17/21 (major)

## Files with Potential Impacts

| File | APIs Used | Impact Type |
|------|-----------|-------------|
| `SecurityConfig.java` | SSLSocket, TrustManager | Security (TLS 1.0/1.1 disabled in 11.0.19+) |
| `LegacySecurityManager.java` | SecurityManager | Deprecated for removal (JDK 17+) |
| `Application.java` | AccessController, Reflection | Deprecated + Module restrictions |

## Testing Scenarios

### Scenario 1: Patch Upgrade (11.0.18 → 11.0.22)

```bash
# Using the Renovate agent
curl -X POST http://localhost:8000/api/agents/renovate/execute/detect_version \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"parameters": {"repository_path": "/path/to/java-subject-repo"}}'

# Get available patches
curl -X POST http://localhost:8000/api/agents/renovate/execute/get_available_patches \
  -d '{"parameters": {"repository_path": "/path/to/java-subject-repo"}}'

# Analyze impact
curl -X POST http://localhost:8000/api/agents/analysis/execute/analyze_impact \
  -d '{"parameters": {"repository_path": "/path/to/java-subject-repo", "from_version": "11.0.18", "to_version": "11.0.22"}}'
```

### Scenario 2: Major Upgrade (11 → 17)

```bash
# Suggest migration path
curl -X POST http://localhost:8000/api/agents/analysis/execute/suggest_upgrade_path \
  -d '{"parameters": {"repository_path": "/path/to/java-subject-repo", "target_version": "17.0.10"}}'

# Get OpenRewrite recipes
curl -X POST http://localhost:8000/api/agents/openrewrite/execute/list_recipes
```

## Expected Impacts

When upgrading from 11.0.18:

1. **TLS Changes (11.0.19+)**: `SecurityConfig.java` uses TLS 1.0/1.1 which are disabled
2. **Security Fixes**: Various CVEs addressed between versions
3. **For JDK 17+**: `SecurityManager` and `AccessController` are deprecated for removal
