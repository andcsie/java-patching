import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  GitBranch,
  Download,
  RefreshCw,
  Trash2,
  ArrowLeft,
  AlertTriangle,
  Bot,
  Cpu,
  Shield,
  ChevronDown,
  ChevronUp,
  CheckCircle,
  XCircle,
  Loader2,
  Sparkles,
  Zap,
  Activity,
  Database,
} from 'lucide-react'
import { repoApi, agentsApi } from '../../services/api'
import { useAnalyses } from '../../hooks/useAnalysis'
import { useLLMProviders } from '../../hooks/useLLMProvider'
import toast from 'react-hot-toast'
import RiskBadge from '../analysis/RiskBadge'
import DiffViewer from '../analysis/DiffViewer'
import { ActivityFeed } from '../trace/ActivityFeed'
import { KnowledgeBasePanel } from '../rag/KnowledgeBasePanel'

interface AgentResult {
  success: boolean
  agent_name: string
  action: string
  data: Record<string, unknown> | null
  error: string | null
  warnings: string[]
  suggested_next_agent: string | null
  suggested_next_action: string | null
  workflow_id?: string
  trace_id?: string
}

export default function RepositoryDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [fromVersion, setFromVersion] = useState('')
  const [toVersion, setToVersion] = useState('')
  const [selectedProvider, setSelectedProvider] = useState('')
  const [agentsPanelOpen, setAgentsPanelOpen] = useState(true)
  const [agentResult, setAgentResult] = useState<AgentResult | null>(null)
  const [agentHistory, setAgentHistory] = useState<AgentResult[]>([])  // Keep history of results
  const [runningAgent, setRunningAgent] = useState<string | null>(null)
  const [lastImpacts, setLastImpacts] = useState<Record<string, unknown>[] | null>(null)
  const [selectedAnalysisId, setSelectedAnalysisId] = useState<string | null>(null)
  const [fixerLimit, setFixerLimit] = useState<number>(10)  // Chunk size for fixes
  const [fixerOffset, setFixerOffset] = useState<number>(0)  // Current offset
  const [pushToRemote, setPushToRemote] = useState<boolean>(false)  // Push branch to remote
  const [createRemotePr, setCreateRemotePr] = useState<boolean>(false)  // Create PR on remote
  const [showActivityFeed, setShowActivityFeed] = useState<boolean>(false)  // Show activity panel
  const [workflowId, setWorkflowId] = useState<string | null>(null)  // Current workflow ID for tracing

  // Derived state: check if tests passed from agent history
  const testsPassed = agentHistory.some(r => r.action === 'run_tests' && r.success && (r.data as any)?.tests_passed === true)
  const testsRan = agentHistory.some(r => r.action === 'run_tests' && r.success)
  const testsFailed = testsRan && !testsPassed

  const { data: providers } = useLLMProviders()
  const { data: analyses } = useAnalyses(id)

  // Fetch available agents (unused but kept for future features)
  useQuery({
    queryKey: ['agents'],
    queryFn: async () => {
      const response = await agentsApi.list()
      return response.data
    },
  })

  // Execute agent action
  const executeAgent = async (
    agentName: string,
    actionName: string,
    params: Record<string, unknown> = {},
    analysisId?: string
  ) => {
    setRunningAgent(`${agentName}:${actionName}`)
    try {
      const response = await agentsApi.execute(agentName, actionName, {
        repository_id: id,
        parameters: params,
        analysis_id: analysisId,  // Pass analysis_id if provided
      })
      setAgentResult(response.data)
      // Add to history (keep last 5)
      setAgentHistory(prev => [response.data, ...prev.slice(0, 4)])

      // Set workflow ID for tracing (auto-show activity feed)
      if (response.data.workflow_id) {
        setWorkflowId(response.data.workflow_id)
        setShowActivityFeed(true)
      }

      // Save impacts and analysis_id for chaining LLM actions
      if (response.data.success && response.data.data) {
        if (actionName === 'analyze_impact' && response.data.data.impacts) {
          setLastImpacts(response.data.data.impacts as Record<string, unknown>[])
          setFixerOffset(0)  // Reset pagination on new analysis
          // Invalidate analyses to refresh the list and get new analysis_id
          queryClient.invalidateQueries({ queryKey: ['analyses', id] })
        } else if (actionName === 'explain_impacts' && response.data.data.impacts) {
          setLastImpacts(response.data.data.impacts as Record<string, unknown>[])
        } else if (actionName === 'generate_fixes' && response.data.data.impacts_with_fixes) {
          setLastImpacts(response.data.data.impacts_with_fixes as Record<string, unknown>[])
          // Update offset for pagination
          const pagination = response.data.data.pagination as { next_offset?: number } | undefined
          if (pagination?.next_offset) {
            setFixerOffset(pagination.next_offset)
          }
        }
      }

      if (response.data.success) {
        toast.success(`${agentName}:${actionName} completed`)
      } else {
        toast.error(response.data.error || 'Action failed')
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Failed to execute agent'
      toast.error(message)
      setAgentResult({
        success: false,
        agent_name: agentName,
        action: actionName,
        data: null,
        error: message,
        warnings: [],
        suggested_next_agent: null,
        suggested_next_action: null,
      })
    } finally {
      setRunningAgent(null)
    }
  }

  const { data: repo, isLoading } = useQuery({
    queryKey: ['repository', id],
    queryFn: async () => {
      const response = await repoApi.get(id!)
      return response.data
    },
    enabled: !!id,
  })

  // Auto-populate version fields when repo loads
  useEffect(() => {
    if (repo) {
      if (repo.current_jdk_version && !fromVersion) {
        setFromVersion(repo.current_jdk_version)
      }
      if (repo.target_jdk_version && !toVersion) {
        setToVersion(repo.target_jdk_version)
      }
    }
  }, [repo])

  const cloneMutation = useMutation({
    mutationFn: async () => {
      const response = await repoApi.clone(id!)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['repository', id] })
      toast.success('Repository cloned')
    },
    onError: () => {
      toast.error('Failed to clone repository')
    },
  })

  const pullMutation = useMutation({
    mutationFn: async () => {
      const response = await repoApi.pull(id!)
      return response.data
    },
    onSuccess: () => {
      toast.success('Repository updated')
    },
    onError: () => {
      toast.error('Failed to pull repository')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async () => {
      await repoApi.delete(id!)
    },
    onSuccess: () => {
      toast.success('Repository deleted')
      navigate('/')
    },
    onError: () => {
      toast.error('Failed to delete repository')
    },
  })

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  if (!repo) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-400">Repository not found</p>
      </div>
    )
  }

  return (
    <div>
      <button
        onClick={() => navigate('/')}
        className="flex items-center text-gray-400 hover:text-white mb-4"
      >
        <ArrowLeft className="h-4 w-4 mr-2" />
        Back to repositories
      </button>

      <div className="card mb-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center">
            <GitBranch className="h-8 w-8 text-blue-500 mr-3" />
            <div>
              <h1 className="text-2xl font-bold text-white">{repo.name}</h1>
              <p className="text-gray-400">{repo.url}</p>
            </div>
          </div>

          <div className="flex space-x-2">
            {!repo.local_path ? (
              <button
                onClick={() => cloneMutation.mutate()}
                disabled={cloneMutation.isPending}
                className="btn btn-primary flex items-center"
              >
                <Download className="h-4 w-4 mr-2" />
                {cloneMutation.isPending ? 'Cloning...' : 'Clone'}
              </button>
            ) : (
              <button
                onClick={() => pullMutation.mutate()}
                disabled={pullMutation.isPending}
                className="btn btn-secondary flex items-center"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                {pullMutation.isPending ? 'Pulling...' : 'Pull'}
              </button>
            )}

            <button
              onClick={() => {
                if (confirm('Are you sure you want to delete this repository?')) {
                  deleteMutation.mutate()
                }
              }}
              className="btn btn-danger flex items-center"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </div>

        {repo.description && (
          <p className="mt-4 text-gray-300">{repo.description}</p>
        )}

        <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <span className="text-gray-400 text-sm">Branch</span>
            <p className="text-white">{repo.branch}</p>
          </div>
          <div>
            <span className="text-gray-400 text-sm">Current JDK</span>
            <p className="text-white">{repo.current_jdk_version || 'Not set'}</p>
          </div>
          <div>
            <span className="text-gray-400 text-sm">Target JDK</span>
            <p className="text-blue-400">{repo.target_jdk_version || 'Not set'}</p>
          </div>
          <div>
            <span className="text-gray-400 text-sm">Status</span>
            <p className="text-white">{repo.local_path ? 'Cloned' : 'Not cloned'}</p>
          </div>
        </div>
      </div>

      {/* Observability Row - Activity Feed and RAG side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Activity Feed Panel */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-white flex items-center">
              <Activity className="h-5 w-5 mr-2 text-green-400" />
              Agent Activity
            </h3>
            {workflowId && (
              <span className="flex items-center text-xs text-green-400">
                <span className="w-2 h-2 bg-green-500 rounded-full mr-1 animate-pulse" />
                Live
              </span>
            )}
          </div>
          {workflowId ? (
            <ActivityFeed workflowId={workflowId} maxEvents={50} />
          ) : (
            <div className="text-center py-8 text-gray-500">
              <Activity className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">Run an agent action to see activity</p>
            </div>
          )}
        </div>

        {/* RAG Knowledge Base Panel */}
        <KnowledgeBasePanel />
      </div>

      {/* Agents Panel */}
      <div className="card mb-6">
        <button
          onClick={() => setAgentsPanelOpen(!agentsPanelOpen)}
          className="w-full flex items-center justify-between text-lg font-medium text-white mb-4"
        >
          <div className="flex items-center">
            <Bot className="h-5 w-5 mr-2 text-purple-400" />
            Agents
          </div>
          {agentsPanelOpen ? (
            <ChevronUp className="h-5 w-5 text-gray-400" />
          ) : (
            <ChevronDown className="h-5 w-5 text-gray-400" />
          )}
        </button>

        {agentsPanelOpen && (
          <div className="space-y-4">
            {/* Version Configuration */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 p-3 bg-gray-800/50 rounded-lg">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">From Version</label>
                <input
                  type="text"
                  value={fromVersion}
                  onChange={(e) => setFromVersion(e.target.value)}
                  className="input text-sm"
                  placeholder="11.0.18"
                  disabled={!repo.local_path}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">To Version</label>
                <input
                  type="text"
                  value={toVersion}
                  onChange={(e) => setToVersion(e.target.value)}
                  className="input text-sm"
                  placeholder="11.0.22"
                  disabled={!repo.local_path}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">LLM Provider</label>
                <select
                  value={selectedProvider}
                  onChange={(e) => setSelectedProvider(e.target.value)}
                  className="input text-sm"
                  disabled={!repo.local_path}
                >
                  <option value="">Default</option>
                  {providers?.map((p) => (
                    <option key={p} value={p}>
                      {p.charAt(0).toUpperCase() + p.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Running Agent Banner */}
            {runningAgent && (
              <div className="bg-blue-900/40 border border-blue-500/50 rounded-md p-4 flex items-center">
                <Loader2 className="h-5 w-5 text-blue-400 animate-spin mr-3" />
                <div>
                  <span className="text-blue-200 font-medium">Running: {runningAgent}</span>
                  <p className="text-blue-300/70 text-sm">Please wait...</p>
                </div>
              </div>
            )}

            {!repo.local_path && (
              <div className="bg-yellow-900/30 border border-yellow-500/50 rounded-md p-3 flex items-center text-sm">
                <AlertTriangle className="h-4 w-4 text-yellow-500 mr-2" />
                <span className="text-yellow-200">Clone repository first to use agents</span>
              </div>
            )}

            {/* Quick Actions */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <button
                onClick={() => executeAgent('renovate', 'detect_version', {
                  repository_path: repo.local_path,
                })}
                disabled={!repo.local_path || runningAgent !== null}
                className="p-3 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-left transition-all"
              >
                <div className="flex items-center mb-1">
                  {runningAgent === 'renovate:detect_version' ? (
                    <Loader2 className="h-4 w-4 text-blue-400 animate-spin mr-2" />
                  ) : (
                    <Cpu className="h-4 w-4 text-blue-400 mr-2" />
                  )}
                  <span className="text-white text-sm font-medium">Detect Version</span>
                </div>
                <p className="text-xs text-gray-400">Scan build files for JDK version</p>
              </button>

              <button
                onClick={() => executeAgent('renovate', 'get_available_patches', {
                  repository_path: repo.local_path,
                })}
                disabled={!repo.local_path || runningAgent !== null}
                className="p-3 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-left transition-all"
              >
                <div className="flex items-center mb-1">
                  {runningAgent === 'renovate:get_available_patches' ? (
                    <Loader2 className="h-4 w-4 text-green-400 animate-spin mr-2" />
                  ) : (
                    <Download className="h-4 w-4 text-green-400 mr-2" />
                  )}
                  <span className="text-white text-sm font-medium">Get Patches</span>
                </div>
                <p className="text-xs text-gray-400">Query Adoptium for updates</p>
              </button>

              <button
                onClick={() => {
                  const from = fromVersion || repo.current_jdk_version || '11.0.18'
                  const to = toVersion || repo.target_jdk_version || '11.0.22'
                  executeAgent('analysis', 'analyze_impact', {
                    repository_path: repo.local_path,
                    from_version: from,
                    to_version: to,
                    skip_llm: true,
                  })
                }}
                disabled={!repo.local_path || runningAgent !== null}
                className="p-3 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-left transition-all"
              >
                <div className="flex items-center mb-1">
                  {runningAgent === 'analysis:analyze_impact' ? (
                    <Loader2 className="h-4 w-4 text-gray-400 animate-spin mr-2" />
                  ) : (
                    <AlertTriangle className="h-4 w-4 text-gray-400 mr-2" />
                  )}
                  <span className="text-white text-sm font-medium">Quick Scan</span>
                </div>
                <p className="text-xs text-gray-400">Fast mode (no LLM)</p>
              </button>

              <button
                onClick={() => {
                  const from = fromVersion || repo.current_jdk_version || '11.0.18'
                  const to = toVersion || repo.target_jdk_version || '11.0.22'
                  executeAgent('analysis', 'get_security_advisories', {
                    from_version: from,
                    to_version: to,
                  })
                }}
                disabled={!repo.local_path || runningAgent !== null}
                className="p-3 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-left transition-all"
              >
                <div className="flex items-center mb-1">
                  {runningAgent === 'analysis:get_security_advisories' ? (
                    <Loader2 className="h-4 w-4 text-red-400 animate-spin mr-2" />
                  ) : (
                    <Shield className="h-4 w-4 text-red-400 mr-2" />
                  )}
                  <span className="text-white text-sm font-medium">Security CVEs</span>
                </div>
                <p className="text-xs text-gray-400">List security fixes between versions</p>
              </button>
            </div>

            {/* Step-by-Step Workflow */}
            <div className="border-t border-gray-700 pt-4 mt-4">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center">
                  <Sparkles className="h-4 w-4 text-purple-400 mr-2" />
                  <span className="text-sm font-medium text-white">Upgrade Workflow</span>
                </div>
              </div>

              {/* Workflow Steps */}
              <div className="flex items-center justify-between mb-4 px-2">
                <div className="flex items-center space-x-1 text-xs flex-wrap gap-y-2">
                  <div className={`flex items-center px-2 py-1 rounded ${lastImpacts || analyses?.length ? 'bg-green-900/50 text-green-400' : 'bg-gray-700 text-gray-400'}`}>
                    <span className="font-mono mr-1">1</span> Analyze
                  </div>
                  <span className="text-gray-600">→</span>
                  <div className={`flex items-center px-2 py-1 rounded ${agentHistory.some(r => r.action === 'generate_fixes' && r.success) ? 'bg-green-900/50 text-green-400' : 'bg-gray-700 text-gray-400'}`}>
                    <span className="font-mono mr-1">2</span> Fix
                  </div>
                  <span className="text-gray-600">→</span>
                  <div className={`flex items-center px-2 py-1 rounded ${agentHistory.some(r => r.action === 'create_patches' && r.success) ? 'bg-green-900/50 text-green-400' : 'bg-gray-700 text-gray-400'}`}>
                    <span className="font-mono mr-1">3</span> Patch
                  </div>
                  <span className="text-gray-600">→</span>
                  <div className={`flex items-center px-2 py-1 rounded ${testsPassed ? 'bg-green-900/50 text-green-400' : testsFailed ? 'bg-red-900/50 text-red-400' : 'bg-gray-700 text-gray-400'}`}>
                    <span className="font-mono mr-1">4</span> Test
                  </div>
                  <span className="text-gray-600">→</span>
                  <div className={`flex items-center px-2 py-1 rounded ${agentHistory.some(r => r.action === 'create_pr' && r.success) ? 'bg-green-900/50 text-green-400' : 'bg-gray-700 text-gray-400'}`}>
                    <span className="font-mono mr-1">5</span> PR
                  </div>
                </div>
                {/* Options */}
                <div className="flex items-center space-x-4 text-xs">
                  <div className="flex items-center space-x-2">
                    <span className="text-gray-500">Batch:</span>
                    <select
                      value={fixerLimit}
                      onChange={(e) => {
                        setFixerLimit(Number(e.target.value))
                        setFixerOffset(0)
                      }}
                      className="bg-gray-700 text-white rounded px-2 py-1 text-xs"
                    >
                      <option value={5}>5</option>
                      <option value={10}>10</option>
                      <option value={25}>25</option>
                      <option value={0}>All</option>
                    </select>
                  </div>
                  <label className="flex items-center space-x-1 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={pushToRemote}
                      onChange={(e) => {
                        setPushToRemote(e.target.checked)
                        if (!e.target.checked) setCreateRemotePr(false)
                      }}
                      className="rounded bg-gray-700 border-gray-600"
                    />
                    <span className="text-gray-400">Push</span>
                  </label>
                  <label className={`flex items-center space-x-1 cursor-pointer ${!pushToRemote ? 'opacity-50' : ''}`}>
                    <input
                      type="checkbox"
                      checked={createRemotePr}
                      onChange={(e) => setCreateRemotePr(e.target.checked)}
                      disabled={!pushToRemote}
                      className="rounded bg-gray-700 border-gray-600"
                    />
                    <span className="text-gray-400">Create PR</span>
                  </label>
                </div>
              </div>

              {/* Current State Info */}
              <div className="mb-4 p-3 bg-gray-800/50 rounded-lg text-xs">
                {agentHistory.some(r => r.action === 'create_pr' && r.success) ? (
                  <p className="text-green-400">
                    ✓ PR branch created and pushed!
                  </p>
                ) : testsPassed ? (
                  <p className="text-green-400">
                    ✓ Tests passed! Ready to create PR branch.
                  </p>
                ) : testsFailed ? (
                  <p className="text-red-400">
                    ✗ Tests failed. Fix issues and re-run tests before creating PR.
                  </p>
                ) : agentHistory.some(r => r.action === 'create_patches' && r.success) ? (
                  <p className="text-green-400">
                    ✓ Patches ready! Next: Run Tests to verify changes.
                  </p>
                ) : lastImpacts ? (
                  <p className="text-green-400">
                    ✓ {lastImpacts.length} impacts • {lastImpacts.filter((i: any) => i.fix && !i.fix.error).length} fixed •
                    Next: {lastImpacts.some((i: any) => i.fix) ? 'Create Patches' : 'Generate Fixes'}
                  </p>
                ) : selectedAnalysisId ? (
                  <p className="text-blue-400">
                    ✓ Using saved analysis: {selectedAnalysisId.slice(0, 8)}...
                  </p>
                ) : analyses?.length ? (
                  <p className="text-blue-400">
                    ✓ {analyses.length} saved analyses available - select one below or run new analysis
                  </p>
                ) : (
                  <p className="text-yellow-500">
                    Start with "Analyze" to find JDK compatibility issues
                  </p>
                )}
              </div>

              {/* Action Buttons */}
              <div className="grid grid-cols-5 gap-3">
                {/* Step 1: Analyze */}
                <button
                  onClick={() => {
                    const from = fromVersion || repo.current_jdk_version || '11.0.18'
                    const to = toVersion || repo.target_jdk_version || '11.0.22'
                    executeAgent('analysis', 'analyze_impact', {
                      repository_path: repo.local_path,
                      from_version: from,
                      to_version: to,
                      llm_provider: selectedProvider || undefined,
                    })
                  }}
                  disabled={!repo.local_path || runningAgent !== null}
                  className="p-3 bg-yellow-900/30 hover:bg-yellow-900/50 border border-yellow-500/30 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-center transition-all"
                >
                  <div className="flex flex-col items-center">
                    {runningAgent === 'analysis:analyze_impact' ? (
                      <Loader2 className="h-5 w-5 text-yellow-400 animate-spin mb-1" />
                    ) : (
                      <span className="text-lg mb-1">1️⃣</span>
                    )}
                    <span className="text-white text-sm font-medium">Analyze</span>
                    <p className="text-xs text-gray-400 mt-1">Find issues</p>
                  </div>
                </button>

                {/* Step 2: Generate Fixes */}
                <button
                  onClick={() => {
                    const analysisToUse = selectedAnalysisId || (analyses?.length ? analyses[0]?.id : null)
                    if (!analysisToUse && !lastImpacts) {
                      toast.error('Run Analyze first')
                      return
                    }
                    executeAgent('fixer', 'generate_fixes', {
                      impacts: lastImpacts || undefined,
                      llm_provider: selectedProvider || undefined,
                      limit: fixerLimit || undefined,
                      offset: fixerOffset,
                    }, analysisToUse || undefined)
                  }}
                  disabled={(!lastImpacts && !selectedAnalysisId && !analyses?.length) || runningAgent !== null}
                  className="p-3 bg-green-900/30 hover:bg-green-900/50 border border-green-500/30 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-center transition-all"
                >
                  <div className="flex flex-col items-center">
                    {runningAgent === 'fixer:generate_fixes' ? (
                      <Loader2 className="h-5 w-5 text-green-400 animate-spin mb-1" />
                    ) : (
                      <span className="text-lg mb-1">2️⃣</span>
                    )}
                    <span className="text-white text-sm font-medium">Fix</span>
                    <p className="text-xs text-gray-400 mt-1">LLM suggestions</p>
                  </div>
                </button>

                {/* Step 3: Create Patches */}
                <button
                  onClick={() => {
                    const analysisToUse = selectedAnalysisId || (analyses?.length ? analyses[0]?.id : null)
                    if (!lastImpacts?.some((i: any) => i.fix)) {
                      toast.error('Run Fix first')
                      return
                    }
                    executeAgent('patcher', 'create_patches', {
                      repository_path: repo.local_path,
                      impacts_with_fixes: lastImpacts || undefined,
                      llm_provider: selectedProvider || undefined,
                    }, analysisToUse || undefined)
                  }}
                  disabled={!lastImpacts?.some((i: any) => i.fix) || runningAgent !== null}
                  className="p-3 bg-orange-900/30 hover:bg-orange-900/50 border border-orange-500/30 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-center transition-all"
                >
                  <div className="flex flex-col items-center">
                    {runningAgent === 'patcher:create_patches' ? (
                      <Loader2 className="h-5 w-5 text-orange-400 animate-spin mb-1" />
                    ) : (
                      <span className="text-lg mb-1">3️⃣</span>
                    )}
                    <span className="text-white text-sm font-medium">Patch</span>
                    <p className="text-xs text-gray-400 mt-1">Generate diffs</p>
                  </div>
                </button>

                {/* Step 4: Run Tests */}
                <button
                  onClick={() => {
                    executeAgent('patcher', 'run_tests', {
                      repository_path: repo.local_path,
                    })
                  }}
                  disabled={!agentHistory.some(r => r.action === 'create_patches' && r.success) || runningAgent !== null}
                  className={`p-3 ${testsFailed ? 'bg-red-900/30 border-red-500/30' : 'bg-purple-900/30 border-purple-500/30'} hover:bg-purple-900/50 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-center transition-all border`}
                >
                  <div className="flex flex-col items-center">
                    {runningAgent === 'patcher:run_tests' ? (
                      <Loader2 className="h-5 w-5 text-purple-400 animate-spin mb-1" />
                    ) : testsPassed ? (
                      <CheckCircle className="h-5 w-5 text-green-400 mb-1" />
                    ) : testsFailed ? (
                      <XCircle className="h-5 w-5 text-red-400 mb-1" />
                    ) : (
                      <span className="text-lg mb-1">4️⃣</span>
                    )}
                    <span className="text-white text-sm font-medium">Test</span>
                    <p className="text-xs text-gray-400 mt-1">{testsPassed ? 'Passed' : testsFailed ? 'Failed' : 'Run tests'}</p>
                  </div>
                </button>

                {/* Step 5: Create PR (requires tests to pass) */}
                <button
                  onClick={() => {
                    const from = fromVersion || repo.current_jdk_version || '11.0.18'
                    const to = toVersion || repo.target_jdk_version || '11.0.22'
                    const patches = agentHistory.find(r => r.action === 'create_patches' && r.success)?.data?.patches
                    if (!patches) {
                      toast.error('Run Patch first')
                      return
                    }
                    executeAgent('patcher', 'create_pr', {
                      repository_path: repo.local_path,
                      patches: patches,
                      from_version: from,
                      to_version: to,
                      push: pushToRemote,
                      create_remote_pr: createRemotePr,
                    })
                  }}
                  disabled={!testsPassed || runningAgent !== null}
                  className="p-3 bg-blue-900/30 hover:bg-blue-900/50 border border-blue-500/30 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-center transition-all"
                  title={!testsPassed ? 'Run tests first - tests must pass before creating PR' : ''}
                >
                  <div className="flex flex-col items-center">
                    {runningAgent === 'patcher:create_pr' ? (
                      <Loader2 className="h-5 w-5 text-blue-400 animate-spin mb-1" />
                    ) : (
                      <span className="text-lg mb-1">5️⃣</span>
                    )}
                    <span className="text-white text-sm font-medium">PR</span>
                    <p className="text-xs text-gray-400 mt-1">{pushToRemote ? (createRemotePr ? 'Push & PR' : 'Push') : 'Branch'}</p>
                  </div>
                </button>
              </div>

              {/* Full Upgrade - One Click */}
              <div className="mt-4">
                <button
                  onClick={() => {
                    const from = fromVersion || repo.current_jdk_version || '11.0.18'
                    const to = toVersion || repo.target_jdk_version || '11.0.22'
                    executeAgent('orchestrator', 'full_upgrade', {
                      repository_path: repo.local_path,
                      from_version: from,
                      to_version: to,
                      llm_provider: selectedProvider || undefined,
                      use_openrewrite: true,
                      include_version_bump: true,
                    })
                  }}
                  disabled={!repo.local_path || runningAgent !== null}
                  className="w-full p-4 bg-gradient-to-r from-purple-900/40 to-blue-900/40 hover:from-purple-900/60 hover:to-blue-900/60 border border-purple-500/40 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-all"
                >
                  <div className="flex items-center justify-center">
                    {runningAgent === 'orchestrator:full_upgrade' ? (
                      <Loader2 className="h-5 w-5 text-purple-400 animate-spin mr-2" />
                    ) : (
                      <Zap className="h-5 w-5 text-purple-400 mr-2" />
                    )}
                    <span className="text-white font-medium">Full Upgrade Pipeline</span>
                    <span className="ml-2 text-xs text-purple-300">(All steps automated)</span>
                  </div>
                </button>
              </div>
            </div>

            {/* More Actions */}
            <details className="group">
              <summary className="cursor-pointer text-sm text-gray-400 hover:text-gray-300 mt-4">
                More actions...
              </summary>
              <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3">
                <button
                  onClick={() => {
                    const target = toVersion || repo.target_jdk_version || '11.0.22'
                    executeAgent('renovate', 'preview_version_bump', {
                      target_version: target,
                    })
                  }}
                  disabled={!repo.local_path || runningAgent !== null}
                  className="p-3 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 rounded-lg text-left"
                >
                  <span className="text-white text-sm">Preview Bump</span>
                  <p className="text-xs text-gray-400">Show diffs</p>
                </button>

                <button
                  onClick={() => executeAgent('openrewrite', 'list_recipes', {})}
                  disabled={runningAgent !== null}
                  className="p-3 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 rounded-lg text-left"
                >
                  <span className="text-white text-sm">List Recipes</span>
                  <p className="text-xs text-gray-400">OpenRewrite migrations</p>
                </button>

                <button
                  onClick={() => {
                    const target = toVersion || repo.target_jdk_version || '17.0.10'
                    executeAgent('analysis', 'suggest_upgrade_path', {
                      target_version: target,
                    })
                  }}
                  disabled={!repo.local_path || runningAgent !== null}
                  className="p-3 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 rounded-lg text-left"
                >
                  <span className="text-white text-sm">Upgrade Path</span>
                  <p className="text-xs text-gray-400">Plan major upgrade</p>
                </button>

                <button
                  onClick={() => executeAgent('renovate', 'generate_config', {})}
                  disabled={!repo.local_path || runningAgent !== null}
                  className="p-3 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 rounded-lg text-left"
                >
                  <span className="text-white text-sm">Generate Config</span>
                  <p className="text-xs text-gray-400">Create renovate.json</p>
                </button>
              </div>
            </details>

            {/* Agent Result */}
            {agentResult && (
              <div className={`mt-4 p-4 rounded-lg ${agentResult.success ? 'bg-green-900/20 border border-green-500/30' : 'bg-red-900/20 border border-red-500/30'}`}>
                <div className="flex items-center mb-2">
                  {agentResult.success ? (
                    <CheckCircle className="h-5 w-5 text-green-400 mr-2" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-400 mr-2" />
                  )}
                  <span className="text-white font-medium">
                    {agentResult.agent_name}:{agentResult.action}
                  </span>
                </div>

                {agentResult.error && (
                  <p className="text-red-400 text-sm mb-2">{agentResult.error}</p>
                )}

                {agentResult.warnings.length > 0 && (
                  <div className="mb-2">
                    {agentResult.warnings.map((w, i) => (
                      <p key={i} className="text-yellow-400 text-sm">⚠ {w}</p>
                    ))}
                  </div>
                )}

                {/* Pagination info for fixer */}
                {agentResult.data?.pagination ? (
                  <div className="mb-3 p-2 bg-gray-800 rounded">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-300">
                        Processed {String((agentResult.data.pagination as any).processed)} of {String((agentResult.data.pagination as any).total_available)} impacts
                      </span>
                      {(agentResult.data.pagination as any).has_more && (
                        <button
                          onClick={() => {
                            const analysisToUse = selectedAnalysisId || (analyses?.length ? analyses[0]?.id : null)
                            executeAgent('fixer', 'generate_fixes', {
                              impacts: lastImpacts || undefined,
                              llm_provider: selectedProvider || undefined,
                              limit: fixerLimit || undefined,
                              offset: (agentResult.data!.pagination as any).next_offset,
                            }, analysisToUse || undefined)
                          }}
                          disabled={runningAgent !== null}
                          className="px-3 py-1 bg-green-600 hover:bg-green-500 text-white text-sm rounded disabled:opacity-50"
                        >
                          Continue ({Number((agentResult.data.pagination as any).total_available) - Number((agentResult.data.pagination as any).next_offset)} remaining)
                        </button>
                      )}
                    </div>
                  </div>
                ) : null}

                {agentResult.data && (
                  <div className="mt-3">
                    {/* Special rendering for patches */}
                    {agentResult.action === 'create_patches' && agentResult.data.patches ? (
                      <div>
                        <h3 className="text-sm font-medium text-white mb-3">Generated Patches</h3>
                        <DiffViewer patches={agentResult.data.patches as any[]} />
                      </div>
                    ) : agentResult.action === 'generate_fixes' && agentResult.data.impacts_with_fixes ? (
                      <div>
                        <h3 className="text-sm font-medium text-white mb-3">
                          Generated Fixes ({(agentResult.data as any).successful_fixes}/{(agentResult.data as any).total_fixes})
                        </h3>
                        <div className="space-y-2 max-h-96 overflow-auto">
                          {(agentResult.data.impacts_with_fixes as any[]).map((impact, i) => (
                            <div key={i} className="p-3 bg-gray-800 rounded-lg text-xs">
                              <div className="flex items-center justify-between mb-2">
                                <span className="text-blue-400 font-medium">
                                  {impact.file_path?.split('/').pop()}:{impact.line_number}
                                </span>
                                {impact.fix?.error ? (
                                  <span className="text-red-400 text-xs">Error</span>
                                ) : impact.fix?.fixed_code ? (
                                  <span className="text-green-400 text-xs">Fixed</span>
                                ) : (
                                  <span className="text-yellow-400 text-xs">Pending</span>
                                )}
                              </div>
                              {impact.fix?.error && (
                                <p className="text-red-400 text-xs mb-2">{impact.fix.error}</p>
                              )}
                              {impact.fix?.explanation && (
                                <p className="text-gray-300 mb-2">{impact.fix.explanation}</p>
                              )}
                              {impact.fix?.fixed_code && (
                                <details>
                                  <summary className="cursor-pointer text-gray-400 hover:text-white">
                                    View fixed code
                                  </summary>
                                  <pre className="mt-2 p-2 bg-green-900/20 rounded text-green-300 overflow-auto">
                                    {impact.fix.fixed_code}
                                  </pre>
                                </details>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <details>
                        <summary className="cursor-pointer text-sm text-gray-400 hover:text-gray-300">
                          Result data
                        </summary>
                        <pre className="mt-2 p-3 bg-gray-900 rounded text-xs text-gray-300 overflow-auto max-h-64">
                          {JSON.stringify(agentResult.data, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                )}

                {agentResult.suggested_next_agent && (
                  <div className="mt-3 pt-3 border-t border-gray-700">
                    <p className="text-sm text-gray-400">Suggested next:</p>
                    <button
                      onClick={() => {
                        if (agentResult.suggested_next_agent && agentResult.suggested_next_action) {
                          executeAgent(
                            agentResult.suggested_next_agent,
                            agentResult.suggested_next_action,
                            {}
                          )
                        }
                      }}
                      className="mt-1 text-blue-400 hover:text-blue-300 text-sm"
                    >
                      → {agentResult.suggested_next_agent}:{agentResult.suggested_next_action}
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Previous Results */}
            {agentHistory.length > 1 && (
              <details className="mt-4">
                <summary className="cursor-pointer text-sm text-gray-400 hover:text-gray-300">
                  Previous results ({agentHistory.length - 1})
                </summary>
                <div className="mt-2 space-y-2">
                  {agentHistory.slice(1).map((result, idx) => (
                    <div
                      key={idx}
                      className={`p-3 rounded-lg text-sm ${
                        result.success ? 'bg-green-900/10 border border-green-500/20' : 'bg-red-900/10 border border-red-500/20'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-gray-300 font-medium">
                          {result.agent_name}:{result.action}
                        </span>
                        <button
                          onClick={() => setAgentResult(result)}
                          className="text-xs text-blue-400 hover:text-blue-300"
                        >
                          View
                        </button>
                      </div>
                      {result.data?.successful_fixes !== undefined && (
                        <span className="text-xs text-gray-400">
                          {String(result.data.successful_fixes)}/{String(result.data.total_fixes)} fixes
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        )}
      </div>

      {/* Analysis History */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium text-white">Analysis History</h2>
          {selectedAnalysisId && (
            <button
              onClick={() => setSelectedAnalysisId(null)}
              className="text-xs text-gray-400 hover:text-white"
            >
              Clear selection
            </button>
          )}
        </div>

        {analyses?.length === 0 ? (
          <p className="text-gray-400">No analyses yet</p>
        ) : (
          <div className="space-y-3">
            {analyses?.map((analysis: any) => (
              <div
                key={analysis.id}
                className={`p-4 rounded-lg cursor-pointer transition-all ${
                  selectedAnalysisId === analysis.id
                    ? 'bg-blue-900/40 border-2 border-blue-500'
                    : 'bg-gray-700 hover:bg-gray-600 border-2 border-transparent'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div
                    className="flex-1"
                    onClick={() => {
                      // Toggle selection
                      if (selectedAnalysisId === analysis.id) {
                        setSelectedAnalysisId(null)
                      } else {
                        setSelectedAnalysisId(analysis.id)
                        toast.success('Analysis selected for fixing/patching')
                      }
                    }}
                  >
                    <span className="text-white font-medium">
                      {analysis.from_version} → {analysis.to_version}
                    </span>
                    <span className="ml-2 text-sm text-gray-400">
                      {new Date(analysis.created_at).toLocaleString()}
                    </span>
                    {selectedAnalysisId === analysis.id && (
                      <span className="ml-2 text-xs text-blue-400">(selected)</span>
                    )}
                  </div>
                  <div className="flex items-center space-x-3">
                    <span className="text-sm text-gray-400">
                      {analysis.total_impacts} impacts
                    </span>
                    <RiskBadge level={analysis.risk_level} score={analysis.risk_score} />
                    <span
                      className={`px-2 py-1 text-xs rounded-full ${
                        analysis.status === 'completed'
                          ? 'bg-green-900/50 text-green-400'
                          : analysis.status === 'running'
                          ? 'bg-blue-900/50 text-blue-400'
                          : analysis.status === 'failed'
                          ? 'bg-red-900/50 text-red-400'
                          : 'bg-gray-600 text-gray-300'
                      }`}
                    >
                      {analysis.status}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        navigate(`/analyses/${analysis.id}`)
                      }}
                      className="text-xs text-blue-400 hover:text-blue-300 px-2"
                    >
                      View →
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
