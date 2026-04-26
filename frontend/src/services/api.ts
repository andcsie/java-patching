import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle token refresh on 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const isAuthEndpoint = error.config?.url?.startsWith('/auth/')
    const isOnLoginPage = window.location.pathname === '/login'

    // Only redirect on 401 if not on login page and not an auth endpoint
    if (error.response?.status === 401 && !isAuthEndpoint && !isOnLoginPage) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Auth
export const authApi = {
  register: (data: { username: string; email?: string; password: string }) =>
    api.post('/auth/register', data),

  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }),

  // SSO
  ssoCallback: (provider: string, code: string) =>
    api.post(`/auth/sso/${provider}/callback`, { code }),

  refresh: (refreshToken: string) =>
    api.post('/auth/refresh', null, { params: { refresh_token: refreshToken } }),

  getMe: () => api.get('/auth/me'),

  updateMe: (data: {
    email?: string
    password?: string
  }) => api.patch('/auth/me', data),
}

// Repositories
export const repoApi = {
  list: () => api.get('/repositories'),

  get: (id: string) => api.get(`/repositories/${id}`),

  create: (data: {
    name: string
    url: string
    description?: string
    branch?: string
    current_jdk_version?: string
    target_jdk_version?: string
  }) => api.post('/repositories', data),

  update: (id: string, data: Partial<{
    name: string
    description: string
    branch: string
    current_jdk_version: string
    target_jdk_version: string
    is_active: boolean
  }>) => api.patch(`/repositories/${id}`, data),

  delete: (id: string) => api.delete(`/repositories/${id}`),

  clone: (id: string) => api.post(`/repositories/${id}/clone`),

  pull: (id: string) => api.post(`/repositories/${id}/pull`),

  detectVersion: (id: string) => api.get(`/repositories/${id}/detect-version`),

  scan: (scanPath?: string) =>
    api.post('/repositories/scan', null, { params: { scan_path: scanPath } }),
}

// Impact Analysis
export const impactApi = {
  startAnalysis: (data: {
    repository_id: string
    from_version: string
    to_version: string
    llm_provider?: string
  }) => api.post('/impact/analyze', data),

  listAnalyses: (repositoryId?: string, limit?: number) =>
    api.get('/impact/analyses', { params: { repository_id: repositoryId, limit } }),

  getAnalysis: (id: string) => api.get(`/impact/analyses/${id}`),

  deleteAnalysis: (id: string) => api.delete(`/impact/analyses/${id}`),
}

// Patches
export const patchApi = {
  getChanges: (fromVersion: string, toVersion: string) =>
    api.get('/patches/changes', { params: { from_version: fromVersion, to_version: toVersion } }),

  getVersions: () => api.get('/patches/versions'),

  getSecurityFixes: (fromVersion: string, toVersion: string) =>
    api.get('/patches/security-fixes', { params: { from_version: fromVersion, to_version: toVersion } }),
}

// Agent
export const agentApi = {
  getProviders: () => api.get('/agent/providers'),

  chat: (data: {
    content: string
    repository_id?: string
    analysis_id?: string
    provider?: string
  }) => api.post('/agent/chat', data),

  chatStream: (data: {
    content: string
    repository_id?: string
    analysis_id?: string
    provider?: string
  }) => {
    const token = localStorage.getItem('access_token')
    return fetch('/api/agent/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    })
  },

  suggestFix: (code: string, issueDescription: string, provider?: string) =>
    api.post('/agent/suggest-fix', null, {
      params: { code, issue_description: issueDescription, provider },
    }),

  explainChange: (changeDescription: string, provider?: string) =>
    api.post('/agent/explain-change', null, {
      params: { change_description: changeDescription, provider },
    }),
}

// Audit
export const auditApi = {
  getLogs: (params?: {
    entity_type?: string
    entity_id?: string
    action?: string
    limit?: number
    offset?: number
  }) => api.get('/audit/logs', { params }),

  getActivity: (limit?: number) =>
    api.get('/audit/activity', { params: { limit } }),

  getHistory: (params?: {
    repository_id?: string
    from_version?: string
    to_version?: string
    limit?: number
    offset?: number
  }) => api.get('/audit/history', { params }),

  getHistoryDetail: (id: string) => api.get(`/audit/history/${id}`),

  getRepositoryHistory: (repositoryId: string, limit?: number) =>
    api.get(`/audit/repository/${repositoryId}/history`, { params: { limit } }),
}

// Agents
export const agentsApi = {
  list: () => api.get('/agents'),

  health: () => api.get('/agents/health'),

  capabilities: () => api.get('/agents/capabilities'),

  tools: () => api.get('/agents/tools'),

  get: (agentName: string) => api.get(`/agents/${agentName}`),

  getActions: (agentName: string) => api.get(`/agents/${agentName}/actions`),

  getAction: (agentName: string, actionName: string) =>
    api.get(`/agents/${agentName}/actions/${actionName}`),

  execute: (agentName: string, actionName: string, params: {
    parameters?: Record<string, unknown>
    repository_id?: string
    analysis_id?: string  // Use existing analysis instead of re-running
  }) => api.post(`/agents/${agentName}/execute/${actionName}`, params),

  executeByCapability: (capability: string, actionName: string, params: {
    parameters?: Record<string, unknown>
    repository_id?: string
  }) => api.post(`/agents/execute-by-capability/${capability}?action_name=${actionName}`, params),
}

// Automation (Renovate-style)
export const automationApi = {
  getJdkVersion: (repositoryId: string) =>
    api.get(`/automation/${repositoryId}/jdk-version`),

  getAvailablePatches: (repositoryId: string) =>
    api.get(`/automation/${repositoryId}/available-patches`),

  previewBump: (repositoryId: string, targetVersion: string) =>
    api.post(`/automation/${repositoryId}/preview-bump`, { target_version: targetVersion }),

  applyBump: (repositoryId: string, targetVersion: string) =>
    api.post(`/automation/${repositoryId}/apply-bump`, { target_version: targetVersion }),

  generateRenovateConfig: (repositoryId: string, targetJdk?: string) =>
    api.post(`/automation/${repositoryId}/generate-renovate-config`, null, {
      params: { target_jdk: targetJdk },
    }),

  saveRenovateConfig: (repositoryId: string, targetJdk?: string) =>
    api.post(`/automation/${repositoryId}/save-renovate-config`, null, {
      params: { target_jdk: targetJdk },
    }),
}

// Traces
export const tracesApi = {
  list: (params?: { repository_id?: string; limit?: number }) =>
    api.get('/traces', { params }),

  get: (traceId: string) => api.get(`/traces/${traceId}`),

  getEvents: (traceId: string) => api.get(`/traces/${traceId}/events`),

  getFull: (traceId: string) => api.get(`/traces/${traceId}/full`),

  getByWorkflow: (workflowId: string) => api.get(`/traces/workflow/${workflowId}`),
}

// RAG Knowledge Base
export const ragApi = {
  getStats: () => api.get('/rag/stats'),

  initialize: () => api.post('/rag/initialize'),

  ingestAllReleaseNotes: () => api.post('/rag/ingest/all-release-notes'),

  ingestVersionRange: (fromVersion: string, toVersion: string) =>
    api.post('/rag/ingest/version-range', { from_version: fromVersion, to_version: toVersion }),

  ingestUrl: (url: string, title?: string, docType?: string, jdkVersions?: string[]) =>
    api.post('/rag/ingest/url', { url, title, doc_type: docType, jdk_versions: jdkVersions }),

  ingestMigrationGuides: () => api.post('/rag/ingest/migration-guides'),

  search: (query: string, collection: 'release_notes' | 'fixes' | 'docs', limit?: number) =>
    api.post('/rag/search', { query, collection, limit }),

  searchReleaseNotes: (query: string, version?: string, changeType?: string, limit?: number) =>
    api.get('/rag/search/release-notes', { params: { query, version, change_type: changeType, limit } }),

  searchFixes: (code: string, changeType?: string, limit?: number) =>
    api.get('/rag/search/fixes', { params: { code, change_type: changeType, limit } }),
}

export default api
