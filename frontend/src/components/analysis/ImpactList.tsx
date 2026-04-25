import { useState } from 'react'
import {
  AlertTriangle,
  AlertCircle,
  Info,
  ChevronDown,
  ChevronRight,
  FileCode,
  Shield,
} from 'lucide-react'
import clsx from 'clsx'

interface Impact {
  id: string
  file_path: string
  line_number?: number
  column_number?: number
  change_type: string
  severity: string
  affected_code?: string
  description: string
  affected_class?: string
  affected_method?: string
  jdk_component?: string
  cve_id?: string
  migration_notes?: string
  suggested_fix?: string
}

interface Props {
  impacts: Impact[]
}

const severityConfig = {
  critical: {
    icon: AlertTriangle,
    color: 'text-red-500',
    bg: 'bg-red-900/30',
    border: 'border-red-500/50',
  },
  high: {
    icon: AlertTriangle,
    color: 'text-orange-500',
    bg: 'bg-orange-900/30',
    border: 'border-orange-500/50',
  },
  medium: {
    icon: AlertCircle,
    color: 'text-yellow-500',
    bg: 'bg-yellow-900/30',
    border: 'border-yellow-500/50',
  },
  low: {
    icon: Info,
    color: 'text-blue-500',
    bg: 'bg-blue-900/30',
    border: 'border-blue-500/50',
  },
}

const changeTypeLabels: Record<string, string> = {
  deprecated: 'Deprecated',
  removed: 'Removed',
  security: 'Security',
  behavioral: 'Behavioral Change',
  bugfix: 'Bug Fix',
  new_feature: 'New Feature',
}

export default function ImpactList({ impacts }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [filter, setFilter] = useState<string>('all')

  const filteredImpacts = impacts.filter((impact) => {
    if (filter === 'all') return true
    return impact.severity === filter
  })

  // Group by severity
  const groupedImpacts = filteredImpacts.reduce(
    (acc, impact) => {
      const severity = impact.severity || 'low'
      if (!acc[severity]) acc[severity] = []
      acc[severity].push(impact)
      return acc
    },
    {} as Record<string, Impact[]>
  )

  const severityOrder = ['critical', 'high', 'medium', 'low']

  return (
    <div>
      {/* Filter */}
      <div className="flex space-x-2 mb-4">
        <button
          onClick={() => setFilter('all')}
          className={clsx(
            'px-3 py-1 rounded-md text-sm',
            filter === 'all' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'
          )}
        >
          All ({impacts.length})
        </button>
        {severityOrder.map((severity) => {
          const count = impacts.filter((i) => i.severity === severity).length
          if (count === 0) return null
          const config = severityConfig[severity as keyof typeof severityConfig]
          return (
            <button
              key={severity}
              onClick={() => setFilter(severity)}
              className={clsx(
                'px-3 py-1 rounded-md text-sm capitalize',
                filter === severity ? `${config.bg} ${config.color}` : 'bg-gray-700 text-gray-300'
              )}
            >
              {severity} ({count})
            </button>
          )
        })}
      </div>

      {/* Impact Items */}
      <div className="space-y-2">
        {severityOrder.map((severity) => {
          const items = groupedImpacts[severity]
          if (!items || items.length === 0) return null

          return items.map((impact) => {
            const config = severityConfig[severity as keyof typeof severityConfig]
            const Icon = config.icon
            const isExpanded = expandedId === impact.id

            return (
              <div
                key={impact.id}
                className={clsx('rounded-lg border', config.bg, config.border)}
              >
                <button
                  onClick={() => setExpandedId(isExpanded ? null : impact.id)}
                  className="w-full p-4 flex items-start text-left"
                >
                  <Icon className={clsx('h-5 w-5 mt-0.5 mr-3 flex-shrink-0', config.color)} />

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-2">
                      <span className={clsx('font-medium', config.color)}>
                        {severity.toUpperCase()}
                      </span>
                      <span className="px-2 py-0.5 bg-gray-700 rounded text-xs text-gray-300">
                        {changeTypeLabels[impact.change_type] || impact.change_type}
                      </span>
                      {impact.cve_id && (
                        <span className="px-2 py-0.5 bg-red-900/50 rounded text-xs text-red-300 flex items-center">
                          <Shield className="h-3 w-3 mr-1" />
                          {impact.cve_id}
                        </span>
                      )}
                    </div>

                    <p className="mt-1 text-gray-300 text-sm line-clamp-2">
                      {impact.description}
                    </p>

                    <div className="mt-2 flex items-center text-xs text-gray-400">
                      <FileCode className="h-3 w-3 mr-1" />
                      <span className="truncate">
                        {impact.file_path}
                        {impact.line_number && `:${impact.line_number}`}
                      </span>
                    </div>
                  </div>

                  {isExpanded ? (
                    <ChevronDown className="h-5 w-5 text-gray-400 ml-2" />
                  ) : (
                    <ChevronRight className="h-5 w-5 text-gray-400 ml-2" />
                  )}
                </button>

                {isExpanded && (
                  <div className="px-4 pb-4 pt-0 border-t border-gray-700/50">
                    <div className="grid grid-cols-2 gap-4 mb-4">
                      {impact.affected_class && (
                        <div>
                          <span className="text-xs text-gray-400">Affected Class</span>
                          <p className="text-sm text-gray-300 font-mono">
                            {impact.affected_class}
                          </p>
                        </div>
                      )}
                      {impact.affected_method && (
                        <div>
                          <span className="text-xs text-gray-400">Affected Method</span>
                          <p className="text-sm text-gray-300 font-mono">
                            {impact.affected_method}
                          </p>
                        </div>
                      )}
                      {impact.jdk_component && (
                        <div>
                          <span className="text-xs text-gray-400">JDK Component</span>
                          <p className="text-sm text-gray-300">{impact.jdk_component}</p>
                        </div>
                      )}
                    </div>

                    {impact.affected_code && (
                      <div className="mb-4">
                        <span className="text-xs text-gray-400">Affected Code</span>
                        <pre className="mt-1 p-3 bg-gray-900 rounded text-sm text-gray-300 overflow-x-auto">
                          <code>{impact.affected_code}</code>
                        </pre>
                      </div>
                    )}

                    {impact.migration_notes && (
                      <div className="mb-4">
                        <span className="text-xs text-gray-400">Migration Notes</span>
                        <p className="mt-1 text-sm text-gray-300">{impact.migration_notes}</p>
                      </div>
                    )}

                    {impact.suggested_fix && (
                      <div>
                        <span className="text-xs text-gray-400">Suggested Fix</span>
                        <pre className="mt-1 p-3 bg-green-900/20 border border-green-500/30 rounded text-sm text-green-300 overflow-x-auto">
                          <code>{impact.suggested_fix}</code>
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })
        })}
      </div>
    </div>
  )
}
