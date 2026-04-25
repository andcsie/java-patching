import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  GitBranch,
  Play,
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
  FileCode,
  Wand2,
  Zap,
} from 'lucide-react'
import { repoApi, agentsApi, automationApi } from '../../services/api'
import { useAnalyses, useStartAnalysis } from '../../hooks/useAnalysis'
import { useLLMProviders } from '../../hooks/useLLMProvider'
import toast from 'react-hot-toast'
import RiskBadge from '../analysis/RiskBadge'

interface AgentResult {
  success: boolean
  agent_name: string
  action: string
  data: Record<string, unknown> | null
  error: string | null
  warnings: string[]
  suggested_next_agent: string | null
  suggested_next_action: string | null
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
  const [runningAgent, setRunningAgent] = useState<string | null>(null)
  const [lastImpacts, setLastImpacts] = useState<Record<string, unknown>[] | null>(null)
  const [selectedAnalysisId, setSelectedAnalysisId] = useState<string | null>(null)
  const [fixerLimit, setFixerLimit] = useState<number>(10)  // Chunk size for fixes
  const [fixerOffset, setFixerOffset] = useState<number>(0)  // Current offset

  const { data: providers } = useLLMProviders()
  const { data: analyses } = useAnalyses(id)
  const startAnalysis = useStartAnalysis()

  // Fetch available agents
  const { data: agents } = useQuery({
    queryKey: ['agents'],
    queryFn: async () => {
      const response = await agentsApi.list()
      return response.data
    },
  })

  // Fetch detected JDK version
  const { data: detectedVersion, refetch: refetchVersion } = useQuery({
    queryKey: ['jdk-version', id],
    queryFn: async () => {
      const response = await automationApi.getJdkVersion(id!)
      return response.data
    },
    enabled: false, // Manual trigger
  })

  // Fetch available patches
  const { data: availablePatches, refetch: refetchPatches } = useQuery({
    queryKey: ['patches', id],
    queryFn: async () => {
      const response = await automationApi.getAvailablePatches(id!)
      return response.data
    },
    enabled: false, // Manual trigger
  })

  // Execute agent action
  const executeAgent = async (
    agentName: string,
    actionName: string,
    params: Record<string, unknown> = {},
    analysisId?: string
  ) => {
    setRunningAgent(`${agentName}:${actionName}`)
    setAgentResult(null)
    try {
      const response = await agentsApi.execute(agentName, actionName, {
        repository_id: id,
        parameters: params,
        analysis_id: analysisId,  // Pass analysis_id if provided
      })
      setAgentResult(response.data)

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

  const handleStartAnalysis = () => {
    if (!fromVersion || !toVersion) {
      toast.error('Please enter both from and to versions')
      return
    }

    startAnalysis.mutate({
      repository_id: id!,
      from_version: fromVersion,
      to_version: toVersion,
      llm_provider: selectedProvider || undefined,
    })
  }

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

      {/* Analysis Form */}
      <div className="card mb-6">
        <h2 className="text-lg font-medium text-white mb-4">Start New Analysis</h2>

        {!repo.local_path && (
          <div className="bg-yellow-900/30 border border-yellow-500/50 rounded-md p-4 mb-4 flex items-center">
            <AlertTriangle className="h-5 w-5 text-yellow-500 mr-2" />
            <span className="text-yellow-200">
              Clone the repository first before starting an analysis
            </span>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              From Version
            </label>
            <input
              type="text"
              value={fromVersion}
              onChange={(e) => setFromVersion(e.target.value)}
              className="input"
              placeholder="11.0.18"
              disabled={!repo.local_path}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              To Version
            </label>
            <input
              type="text"
              value={toVersion}
              onChange={(e) => setToVersion(e.target.value)}
              className="input"
              placeholder="11.0.22"
              disabled={!repo.local_path}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              LLM Provider
            </label>
            <select
              value={selectedProvider}
              onChange={(e) => setSelectedProvider(e.target.value)}
              className="input"
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
          <div className="flex items-end">
            <button
              onClick={handleStartAnalysis}
              disabled={!repo.local_path || startAnalysis.isPending}
              className="btn btn-primary w-full flex items-center justify-center"
            >
              <Play className="h-4 w-4 mr-2" />
              {startAnalysis.isPending ? 'Starting...' : 'Analyze'}
            </button>
          </div>
        </div>
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
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
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
                    llm_provider: selectedProvider || undefined,
                  })
                }}
                disabled={!repo.local_path || runningAgent !== null}
                className="p-3 bg-yellow-900/30 hover:bg-yellow-900/50 border border-yellow-500/30 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-left transition-all"
              >
                <div className="flex items-center mb-1">
                  {runningAgent === 'analysis:analyze_impact' ? (
                    <Loader2 className="h-4 w-4 text-yellow-400 animate-spin mr-2" />
                  ) : (
                    <Sparkles className="h-4 w-4 text-yellow-400 mr-2" />
                  )}
                  <span className="text-white text-sm font-medium">Analyze Impact</span>
                </div>
                <p className="text-xs text-gray-400">Scan code + LLM explanations</p>
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

            {/* Separate Agent Actions */}
            <div className="border-t border-gray-700 pt-4 mt-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center">
                  <Sparkles className="h-4 w-4 text-purple-400 mr-2" />
                  <span className="text-sm font-medium text-purple-400">Code Transformation (Separate Agents)</span>
                </div>
                {/* Chunking controls */}
                <div className="flex items-center space-x-2 text-xs">
                  <span className="text-gray-400">Batch:</span>
                  <select
                    value={fixerLimit}
                    onChange={(e) => {
                      setFixerLimit(Number(e.target.value))
                      setFixerOffset(0)  // Reset offset when changing batch size
                    }}
                    className="bg-gray-700 text-white rounded px-2 py-1 text-xs"
                  >
                    <option value={5}>5</option>
                    <option value={10}>10</option>
                    <option value={25}>25</option>
                    <option value={50}>50</option>
                    <option value={0}>All</option>
                  </select>
                  {fixerOffset > 0 && (
                    <button
                      onClick={() => setFixerOffset(0)}
                      className="text-blue-400 hover:text-blue-300"
                    >
                      Reset
                    </button>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <button
                  onClick={() => {
                    // Use selected analysis from history, or require in-memory impacts
                    const analysisToUse = selectedAnalysisId || (analyses?.length ? analyses[0]?.id : null)
                    if (!analysisToUse && !lastImpacts) {
                      toast.error('Run "Analyze Impact" first or select an analysis from history')
                      return
                    }
                    executeAgent('fixer', 'generate_fixes', {
                      impacts: lastImpacts || undefined,  // Only pass if we have in-memory
                      llm_provider: selectedProvider || undefined,
                      limit: fixerLimit || undefined,  // 0 means no limit
                      offset: fixerOffset,
                    }, analysisToUse || undefined)
                  }}
                  disabled={(!lastImpacts && !selectedAnalysisId && !analyses?.length) || runningAgent !== null}
                  className="p-3 bg-green-900/30 hover:bg-green-900/50 border border-green-500/30 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-left transition-all"
                >
                  <div className="flex items-center mb-1">
                    {runningAgent === 'fixer:generate_fixes' ? (
                      <Loader2 className="h-4 w-4 text-green-400 animate-spin mr-2" />
                    ) : (
                      <Wand2 className="h-4 w-4 text-green-400 mr-2" />
                    )}
                    <span className="text-white text-sm font-medium">Generate Fixes</span>
                  </div>
                  <p className="text-xs text-gray-400">
                    {fixerLimit > 0 ? `Process ${fixerLimit} impacts` : 'Process all impacts'}
                    {fixerOffset > 0 && ` (from #${fixerOffset + 1})`}
                  </p>
                </button>

                <button
                  onClick={() => {
                    // Use selected analysis from history, or require in-memory impacts
                    const analysisToUse = selectedAnalysisId || (analyses?.length ? analyses[0]?.id : null)
                    if (!analysisToUse && !lastImpacts) {
                      toast.error('Run "Generate Fixes" first or select an analysis from history')
                      return
                    }
                    executeAgent('patcher', 'create_patches', {
                      repository_path: repo.local_path,
                      impacts_with_fixes: lastImpacts || undefined,
                      llm_provider: selectedProvider || undefined,
                    }, analysisToUse || undefined)
                  }}
                  disabled={(!lastImpacts && !selectedAnalysisId && !analyses?.length) || runningAgent !== null}
                  className="p-3 bg-orange-900/30 hover:bg-orange-900/50 border border-orange-500/30 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-left transition-all"
                >
                  <div className="flex items-center mb-1">
                    {runningAgent === 'patcher:create_patches' ? (
                      <Loader2 className="h-4 w-4 text-orange-400 animate-spin mr-2" />
                    ) : (
                      <FileCode className="h-4 w-4 text-orange-400 mr-2" />
                    )}
                    <span className="text-white text-sm font-medium">Create Patches</span>
                  </div>
                  <p className="text-xs text-gray-400">Generate unified diffs</p>
                </button>

                <button
                  onClick={() => {
                    const from = fromVersion || repo.current_jdk_version || '11.0.18'
                    const to = toVersion || repo.target_jdk_version || '11.0.22'
                    executeAgent('orchestrator', 'full_upgrade', {
                      repository_path: repo.local_path,
                      from_version: from,
                      to_version: to,
                      llm_provider: selectedProvider || undefined,
                    })
                  }}
                  disabled={!repo.local_path || runningAgent !== null}
                  className="p-3 bg-purple-900/30 hover:bg-purple-900/50 border border-purple-500/30 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-left transition-all"
                >
                  <div className="flex items-center mb-1">
                    {runningAgent === 'orchestrator:full_upgrade' ? (
                      <Loader2 className="h-4 w-4 text-purple-400 animate-spin mr-2" />
                    ) : (
                      <Zap className="h-4 w-4 text-purple-400 mr-2" />
                    )}
                    <span className="text-white text-sm font-medium">Full Upgrade</span>
                  </div>
                  <p className="text-xs text-gray-400">Orchestrate all agents</p>
                </button>
              </div>

              <div className="mt-3 p-3 bg-gray-800/50 rounded-lg">
                <p className="text-xs text-gray-400">
                  <strong className="text-gray-300">Workflow:</strong> Analyze Impact (+ LLM explanations) → Generate Fixes → Create Patches
                </p>
                {selectedAnalysisId && (
                  <p className="text-xs text-blue-400 mt-1">
                    ✓ Using analysis: {selectedAnalysisId.slice(0, 8)}...
                  </p>
                )}
                {!lastImpacts && !selectedAnalysisId && analyses?.length ? (
                  <p className="text-xs text-blue-400 mt-1">
                    ✓ Will use latest analysis from history
                  </p>
                ) : !lastImpacts && !selectedAnalysisId && !analyses?.length ? (
                  <p className="text-xs text-yellow-500 mt-1">
                    ⚠ Run "Analyze Impact" first to enable fixing and patching
                  </p>
                ) : null}
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
                {agentResult.data?.pagination && (
                  <div className="mb-3 p-2 bg-gray-800 rounded">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-300">
                        Processed {(agentResult.data.pagination as any).processed} of {(agentResult.data.pagination as any).total_available} impacts
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
                          Continue ({(agentResult.data.pagination as any).total_available - (agentResult.data.pagination as any).next_offset} remaining)
                        </button>
                      )}
                    </div>
                  </div>
                )}

                {agentResult.data && (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-sm text-gray-400 hover:text-gray-300">
                      Result data
                    </summary>
                    <pre className="mt-2 p-3 bg-gray-900 rounded text-xs text-gray-300 overflow-auto max-h-64">
                      {JSON.stringify(agentResult.data, null, 2)}
                    </pre>
                  </details>
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
