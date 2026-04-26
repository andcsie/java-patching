import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Database, Search, Upload, RefreshCw, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import { ragApi } from '../../services/api'
import toast from 'react-hot-toast'

export function KnowledgeBasePanel() {
  const [searchQuery, setSearchQuery] = useState('')
  const [searchCollection, setSearchCollection] = useState<'release_notes' | 'fixes' | 'docs'>('release_notes')
  const [searchResults, setSearchResults] = useState<any[]>([])

  // Get RAG stats
  const { data: stats, isLoading: statsLoading, refetch: refetchStats } = useQuery({
    queryKey: ['rag-stats'],
    queryFn: async () => {
      const response = await ragApi.getStats()
      return response.data
    },
  })

  // Initialize RAG
  const initMutation = useMutation({
    mutationFn: () => ragApi.initialize(),
    onSuccess: () => {
      toast.success('RAG collections initialized')
      refetchStats()
    },
    onError: () => toast.error('Failed to initialize RAG'),
  })

  // Ingest all release notes
  const ingestAllMutation = useMutation({
    mutationFn: () => ragApi.ingestAllReleaseNotes(),
    onSuccess: (response) => {
      toast.success(`Indexed ${response.data.indexed} release notes`)
      refetchStats()
    },
    onError: () => toast.error('Failed to ingest release notes'),
  })

  // Ingest migration guides
  const ingestGuidesMutation = useMutation({
    mutationFn: () => ragApi.ingestMigrationGuides(),
    onSuccess: (response) => {
      toast.success(`Indexed ${response.data.total_indexed} guides`)
      refetchStats()
    },
    onError: () => toast.error('Failed to ingest guides'),
  })

  // Search
  const searchMutation = useMutation({
    mutationFn: () => ragApi.search(searchQuery, searchCollection, 5),
    onSuccess: (response) => {
      setSearchResults(response.data.results || [])
      if (response.data.results?.length === 0) {
        toast('No results found', { icon: '🔍' })
      }
    },
    onError: () => toast.error('Search failed'),
  })

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      searchMutation.mutate()
    }
  }

  const isAnyLoading = initMutation.isPending || ingestAllMutation.isPending || ingestGuidesMutation.isPending

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-medium text-white flex items-center">
          <Database className="h-5 w-5 mr-2 text-purple-400" />
          RAG Knowledge Base
        </h2>
        <button
          onClick={() => refetchStats()}
          className="text-gray-400 hover:text-white"
          title="Refresh stats"
        >
          <RefreshCw className={`h-4 w-4 ${statsLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        {statsLoading ? (
          <div className="col-span-3 text-center py-4">
            <Loader2 className="h-5 w-5 animate-spin mx-auto text-gray-400" />
          </div>
        ) : stats?.status === 'error' ? (
          <div className="col-span-3 p-3 bg-red-900/30 border border-red-500/30 rounded-lg text-sm text-red-300">
            <AlertCircle className="h-4 w-4 inline mr-2" />
            Qdrant not connected. Make sure it's running on port 6333.
          </div>
        ) : (
          <>
            <div className="p-3 bg-gray-800 rounded-lg">
              <p className="text-xs text-gray-400">Release Notes</p>
              <p className="text-xl font-bold text-white">
                {stats?.collections?.jdk_release_notes?.points_count || 0}
              </p>
            </div>
            <div className="p-3 bg-gray-800 rounded-lg">
              <p className="text-xs text-gray-400">Fixes</p>
              <p className="text-xl font-bold text-white">
                {stats?.collections?.successful_fixes?.points_count || 0}
              </p>
            </div>
            <div className="p-3 bg-gray-800 rounded-lg">
              <p className="text-xs text-gray-400">Documentation</p>
              <p className="text-xl font-bold text-white">
                {stats?.collections?.documentation?.points_count || 0}
              </p>
            </div>
          </>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-2 mb-4">
        <button
          onClick={() => initMutation.mutate()}
          disabled={isAnyLoading}
          className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 rounded text-sm text-white flex items-center"
        >
          {initMutation.isPending ? (
            <Loader2 className="h-4 w-4 mr-1 animate-spin" />
          ) : (
            <CheckCircle className="h-4 w-4 mr-1" />
          )}
          Initialize
        </button>
        <button
          onClick={() => ingestAllMutation.mutate()}
          disabled={isAnyLoading}
          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded text-sm text-white flex items-center"
        >
          {ingestAllMutation.isPending ? (
            <Loader2 className="h-4 w-4 mr-1 animate-spin" />
          ) : (
            <Upload className="h-4 w-4 mr-1" />
          )}
          Ingest JDK Release Notes
        </button>
        <button
          onClick={() => ingestGuidesMutation.mutate()}
          disabled={isAnyLoading}
          className="px-3 py-1.5 bg-green-600 hover:bg-green-500 disabled:opacity-50 rounded text-sm text-white flex items-center"
        >
          {ingestGuidesMutation.isPending ? (
            <Loader2 className="h-4 w-4 mr-1 animate-spin" />
          ) : (
            <Upload className="h-4 w-4 mr-1" />
          )}
          Ingest Migration Guides
        </button>
      </div>

      {/* Search */}
      <form onSubmit={handleSearch} className="mb-4">
        <div className="flex gap-2">
          <select
            value={searchCollection}
            onChange={(e) => setSearchCollection(e.target.value as any)}
            className="bg-gray-700 text-white rounded px-3 py-2 text-sm"
          >
            <option value="release_notes">Release Notes</option>
            <option value="fixes">Fixes</option>
            <option value="docs">Documentation</option>
          </select>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search knowledge base..."
            className="flex-1 bg-gray-700 text-white rounded px-3 py-2 text-sm placeholder-gray-400"
          />
          <button
            type="submit"
            disabled={searchMutation.isPending || !searchQuery.trim()}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 rounded text-white flex items-center"
          >
            {searchMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Search className="h-4 w-4" />
            )}
          </button>
        </div>
      </form>

      {/* Search Results */}
      {searchResults.length > 0 && (
        <div className="space-y-2 max-h-64 overflow-y-auto">
          <p className="text-xs text-gray-400 mb-2">{searchResults.length} results</p>
          {searchResults.map((result, idx) => (
            <div key={idx} className="p-3 bg-gray-800 rounded-lg text-sm">
              <div className="flex items-center justify-between mb-1">
                <span className="text-purple-400 font-medium">
                  {result.version || result.title || 'Result'}
                </span>
                <span className="text-xs text-gray-500">
                  Score: {(result._score * 100).toFixed(0)}%
                </span>
              </div>
              {result.change_type && (
                <span className="text-xs px-1.5 py-0.5 bg-blue-900/50 text-blue-300 rounded mr-2">
                  {result.change_type}
                </span>
              )}
              <p className="text-gray-300 text-xs mt-1 line-clamp-2">
                {result.description || result.content || JSON.stringify(result).slice(0, 200)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default KnowledgeBasePanel
