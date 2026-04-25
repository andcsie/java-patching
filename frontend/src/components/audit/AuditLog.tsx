import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileText, Clock, Filter } from 'lucide-react'
import { auditApi } from '../../services/api'

interface AuditEntry {
  id: string
  user_id?: string
  action: string
  entity_type: string
  entity_id?: string
  details?: Record<string, unknown>
  ip_address?: string
  user_agent?: string
  created_at: string
}

export default function AuditLog() {
  const [filter, setFilter] = useState({
    action: '',
    entity_type: '',
  })

  const { data: logs, isLoading } = useQuery({
    queryKey: ['audit-logs', filter],
    queryFn: async () => {
      const response = await auditApi.getLogs({
        action: filter.action || undefined,
        entity_type: filter.entity_type || undefined,
        limit: 100,
      })
      return response.data as AuditEntry[]
    },
  })

  const actionColors: Record<string, string> = {
    login_success: 'text-green-400',
    login_failed: 'text-red-400',
    repository_created: 'text-blue-400',
    repository_updated: 'text-yellow-400',
    repository_deleted: 'text-red-400',
    repository_cloned: 'text-purple-400',
    analysis_started: 'text-blue-400',
    analysis_completed: 'text-green-400',
  }

  const uniqueActions = [...new Set(logs?.map((l) => l.action) || [])]
  const uniqueEntityTypes = [...new Set(logs?.map((l) => l.entity_type) || [])]

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Audit Log</h1>
          <p className="text-gray-400 mt-1">Track all actions in your account</p>
        </div>
      </div>

      {/* Filters */}
      <div className="card mb-6">
        <div className="flex items-center space-x-4">
          <Filter className="h-5 w-5 text-gray-400" />
          <select
            value={filter.action}
            onChange={(e) => setFilter({ ...filter, action: e.target.value })}
            className="input w-48"
          >
            <option value="">All Actions</option>
            {uniqueActions.map((action) => (
              <option key={action} value={action}>
                {action.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
          <select
            value={filter.entity_type}
            onChange={(e) => setFilter({ ...filter, entity_type: e.target.value })}
            className="input w-48"
          >
            <option value="">All Entity Types</option>
            {uniqueEntityTypes.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Log Entries */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>
      ) : logs?.length === 0 ? (
        <div className="card text-center py-12">
          <FileText className="h-12 w-12 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-400">No audit entries found</p>
        </div>
      ) : (
        <div className="card">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-gray-400 text-sm border-b border-gray-700">
                  <th className="pb-3 font-medium">Timestamp</th>
                  <th className="pb-3 font-medium">Action</th>
                  <th className="pb-3 font-medium">Entity</th>
                  <th className="pb-3 font-medium">Details</th>
                  <th className="pb-3 font-medium">IP Address</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {logs?.map((entry) => (
                  <tr key={entry.id} className="text-sm">
                    <td className="py-3 text-gray-300">
                      <div className="flex items-center">
                        <Clock className="h-4 w-4 text-gray-500 mr-2" />
                        {new Date(entry.created_at).toLocaleString()}
                      </div>
                    </td>
                    <td className="py-3">
                      <span
                        className={`font-medium ${
                          actionColors[entry.action] || 'text-gray-300'
                        }`}
                      >
                        {entry.action.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="py-3 text-gray-300">
                      <span className="px-2 py-0.5 bg-gray-700 rounded text-xs">
                        {entry.entity_type}
                      </span>
                      {entry.entity_id && (
                        <span className="ml-2 text-gray-500 text-xs">
                          {entry.entity_id.slice(0, 8)}...
                        </span>
                      )}
                    </td>
                    <td className="py-3 text-gray-400 max-w-xs truncate">
                      {entry.details && (
                        <code className="text-xs">
                          {JSON.stringify(entry.details).slice(0, 50)}
                          {JSON.stringify(entry.details).length > 50 && '...'}
                        </code>
                      )}
                    </td>
                    <td className="py-3 text-gray-500 text-xs">{entry.ip_address}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
