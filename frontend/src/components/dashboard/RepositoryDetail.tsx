import { useState } from 'react'
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
} from 'lucide-react'
import { repoApi } from '../../services/api'
import { useAnalyses, useStartAnalysis } from '../../hooks/useAnalysis'
import { useLLMProviders } from '../../hooks/useLLMProvider'
import toast from 'react-hot-toast'
import RiskBadge from '../analysis/RiskBadge'

export default function RepositoryDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [fromVersion, setFromVersion] = useState('')
  const [toVersion, setToVersion] = useState('')
  const [selectedProvider, setSelectedProvider] = useState('')

  const { data: providers } = useLLMProviders()
  const { data: analyses } = useAnalyses(id)
  const startAnalysis = useStartAnalysis()

  const { data: repo, isLoading } = useQuery({
    queryKey: ['repository', id],
    queryFn: async () => {
      const response = await repoApi.get(id!)
      return response.data
    },
    enabled: !!id,
  })

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

      {/* Analysis History */}
      <div className="card">
        <h2 className="text-lg font-medium text-white mb-4">Analysis History</h2>

        {analyses?.length === 0 ? (
          <p className="text-gray-400">No analyses yet</p>
        ) : (
          <div className="space-y-3">
            {analyses?.map((analysis: any) => (
              <div
                key={analysis.id}
                onClick={() => navigate(`/analyses/${analysis.id}`)}
                className="p-4 bg-gray-700 rounded-lg hover:bg-gray-600 cursor-pointer"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-white font-medium">
                      {analysis.from_version} → {analysis.to_version}
                    </span>
                    <span className="ml-2 text-sm text-gray-400">
                      {new Date(analysis.created_at).toLocaleString()}
                    </span>
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
