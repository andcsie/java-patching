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
    if (error.response?.status === 401) {
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

  sshChallenge: (username: string) =>
    api.post('/auth/ssh/challenge', { username }),

  sshVerify: (username: string, challenge: string, signature: string) =>
    api.post('/auth/ssh/verify', { username, challenge, signature }),

  refresh: (refreshToken: string) =>
    api.post('/auth/refresh', null, { params: { refresh_token: refreshToken } }),

  getMe: () => api.get('/auth/me'),

  updateMe: (data: {
    email?: string
    password?: string
    ssh_public_key?: string
    preferred_auth_method?: string
  }) => api.patch('/auth/me', data),

  switchAuthMethod: (method: string) =>
    api.post('/auth/me/switch-auth-method', null, { params: { method } }),
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

export default api
