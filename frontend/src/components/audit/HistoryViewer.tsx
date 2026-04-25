import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { History, Filter, Eye } from 'lucide-react'
import { auditApi } from '../../services/api'
import RiskBadge from '../analysis/RiskBadge'

interface HistoryEntry {
  id: string
  analysis_id: string
  repository_id: string
  user_id: string
  from_version: string
  to_version: string
  risk_score?: number
  risk_level?: string
  total_impacts: number
  high_severity_count: number
  medium_severity_count: number
  low_severity_count: number
  full_report?: Record<string, unknown>
  created_at: string
}

export default function HistoryViewer() {
  const navigate = useNavigate()
  const [fromVersion, setFromVersion] = useState('')
  const [toVersion, setToVersion] = useState('')

  const { data: history, isLoading } = useQuery({
    queryKey: ['analysis-history', fromVersion, toVersion],
    queryFn: async () => {
      const response = await auditApi.getHistory({
        from_version: fromVersion || undefined,
        to_version: toVersion || undefined,
        limit: 100,
      })
      return response.data as HistoryEntry[]
    },
  })

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Analysis History</h1>
          <p className="text-gray-400 mt-1">
            View all past analyses and their results
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="card mb-6">
        <div className="flex items-center space-x-4">
          <Filter className="h-5 w-5 text-gray-400" />
          <input
            type="text"
            value={fromVersion}
            onChange={(e) => setFromVersion(e.target.value)}
            placeholder="From version (e.g., 11.0.18)"
            className="input w-48"
          />
          <span className="text-gray-400">→</span>
          <input
            type="text"
            value={toVersion}
            onChange={(e) => setToVersion(e.target.value)}
            placeholder="To version (e.g., 11.0.22)"
            className="input w-48"
          />
        </div>
      </div>

      {/* History Entries */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>
      ) : history?.length === 0 ? (
        <div className="card text-center py-12">
          <History className="h-12 w-12 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-400">No analysis history found</p>
        </div>
      ) : (
        <div className="space-y-4">
          {history?.map((entry) => (
            <div key={entry.id} className="card">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <div>
                    <h3 className="text-lg font-medium text-white">
                      {entry.from_version} → {entry.to_version}
                    </h3>
                    <p className="text-sm text-gray-400">
                      {new Date(entry.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-4">
                  <RiskBadge level={entry.risk_level} score={entry.risk_score} />

                  <button
                    onClick={() => navigate(`/analyses/${entry.analysis_id}`)}
                    className="btn btn-secondary flex items-center"
                  >
                    <Eye className="h-4 w-4 mr-2" />
                    View
                  </button>
                </div>
              </div>

              <div className="mt-4 grid grid-cols-4 gap-4">
                <div className="bg-gray-700 rounded-lg p-3 text-center">
                  <span className="text-2xl font-bold text-white">
                    {entry.total_impacts}
                  </span>
                  <p className="text-xs text-gray-400">Total Impacts</p>
                </div>
                <div className="bg-gray-700 rounded-lg p-3 text-center">
                  <span className="text-2xl font-bold text-red-400">
                    {entry.high_severity_count}
                  </span>
                  <p className="text-xs text-gray-400">High Severity</p>
                </div>
                <div className="bg-gray-700 rounded-lg p-3 text-center">
                  <span className="text-2xl font-bold text-yellow-400">
                    {entry.medium_severity_count}
                  </span>
                  <p className="text-xs text-gray-400">Medium Severity</p>
                </div>
                <div className="bg-gray-700 rounded-lg p-3 text-center">
                  <span className="text-2xl font-bold text-green-400">
                    {entry.low_severity_count}
                  </span>
                  <p className="text-xs text-gray-400">Low Severity</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
