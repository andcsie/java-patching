#!/bin/bash
# End-to-End Demo Script for Java Patching Application
#
# Prerequisites:
# 1. Backend running: cd backend && uvicorn app.main:app --reload
# 2. PostgreSQL running: docker-compose -f docker-compose.dev.yml up -d
# 3. Admin user created: cd backend && python scripts/seed_admin.py

set -e

API_BASE="http://localhost:8000/api"
REPO_PATH="/Users/andreirizea/hack/JavaPatching/java-subject-repo"

echo "=================================="
echo "Java Patching E2E Demo"
echo "=================================="
echo ""

# Step 1: Login
echo "Step 1: Logging in..."
TOKEN=$(curl -s -X POST "$API_BASE/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}' | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
  echo "ERROR: Login failed. Make sure:"
  echo "  1. Backend is running (uvicorn app.main:app --reload)"
  echo "  2. Admin user exists (python scripts/seed_admin.py)"
  echo "  3. Admin email is valid (python scripts/fix_admin_email.py)"
  exit 1
fi
echo "Logged in successfully!"
echo ""

# Step 2: Create repository
echo "Step 2: Creating repository..."
REPO_RESPONSE=$(curl -s -X POST "$API_BASE/repositories" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"java-subject-repo\",
    \"url\": \"file://$REPO_PATH\",
    \"description\": \"Sample repo for JDK upgrade testing\",
    \"current_jdk_version\": \"11.0.18\",
    \"target_jdk_version\": \"11.0.22\"
  }")

REPO_ID=$(echo $REPO_RESPONSE | jq -r '.id')
if [ "$REPO_ID" == "null" ]; then
  # Repository might already exist, try to get it
  echo "Repository may already exist, fetching..."
  REPO_RESPONSE=$(curl -s "$API_BASE/repositories" -H "Authorization: Bearer $TOKEN")
  REPO_ID=$(echo $REPO_RESPONSE | jq -r '.[0].id')
fi
echo "Repository ID: $REPO_ID"
echo ""

# Step 3: List available agents
echo "Step 3: Listing available agents..."
curl -s "$API_BASE/agents" -H "Authorization: Bearer $TOKEN" | jq '.[] | {name, description}'
echo ""

# Step 4: Detect JDK version using Renovate agent
echo "Step 4: Detecting JDK version..."
curl -s -X POST "$API_BASE/agents/renovate/execute/detect_version" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"parameters\": {\"repository_path\": \"$REPO_PATH\"}}" | jq '.data'
echo ""

# Step 5: Get available patches
echo "Step 5: Getting available patches from Adoptium..."
curl -s -X POST "$API_BASE/agents/renovate/execute/get_available_patches" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"parameters\": {\"repository_path\": \"$REPO_PATH\"}}" | jq '.data.patches[:3]'
echo ""

# Step 6: Get release notes between versions
echo "Step 6: Fetching release notes (11.0.18 → 11.0.22)..."
curl -s -X POST "$API_BASE/agents/analysis/execute/get_release_notes" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"parameters": {"from_version": "11.0.18", "to_version": "11.0.22"}}' | jq '{total_changes: .data.total_changes, by_type: .data.by_type}'
echo ""

# Step 7: Analyze impact
echo "Step 7: Running impact analysis..."
IMPACT=$(curl -s -X POST "$API_BASE/agents/analysis/execute/analyze_impact" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"parameters\": {\"repository_path\": \"$REPO_PATH\", \"from_version\": \"11.0.18\", \"to_version\": \"11.0.22\"}}")

echo "Impact Analysis Results:"
echo $IMPACT | jq '{
  success: .success,
  risk_score: .data.risk_score,
  risk_level: .data.risk_level,
  total_files: .data.total_files_analyzed,
  total_impacts: .data.total_impacts,
  summary: .data.summary
}'
echo ""

# Step 8: Get security advisories
echo "Step 8: Checking security advisories..."
curl -s -X POST "$API_BASE/agents/analysis/execute/get_security_advisories" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"parameters": {"from_version": "11.0.18", "to_version": "11.0.22"}}' | jq '{total_fixes: .data.total_security_fixes, cves: .data.cves}'
echo ""

# Step 9: Preview version bump
echo "Step 9: Previewing version bump..."
curl -s -X POST "$API_BASE/agents/renovate/execute/preview_version_bump" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"parameters\": {\"repository_path\": \"$REPO_PATH\", \"target_version\": \"11.0.22\"}}" | jq '.data.changes'
echo ""

# Step 10: Suggest upgrade path for major version
echo "Step 10: Suggesting upgrade path to JDK 17..."
curl -s -X POST "$API_BASE/agents/analysis/execute/suggest_upgrade_path" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"parameters\": {\"repository_path\": \"$REPO_PATH\", \"target_version\": \"17.0.10\"}}" | jq '.data'
echo ""

echo "=================================="
echo "Demo Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "  - Apply version bump: POST /api/agents/renovate/execute/apply_version_bump"
echo "  - Use chat: POST /api/agent/chat with questions about the impacts"
echo "  - For major upgrade, use OpenRewrite recipes"
