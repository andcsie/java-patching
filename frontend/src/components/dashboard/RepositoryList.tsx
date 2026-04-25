import { Link } from 'react-router-dom'
import { GitBranch, Clock, AlertTriangle, CheckCircle } from 'lucide-react'
import clsx from 'clsx'

interface Repository {
  id: string
  name: string
  url: string
  description?: string
  branch: string
  current_jdk_version?: string
  target_jdk_version?: string
  is_active: boolean
  last_analyzed_at?: string
  created_at: string
}

interface Props {
  repositories: Repository[]
}

export default function RepositoryList({ repositories }: Props) {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {repositories.map((repo) => (
        <Link
          key={repo.id}
          to={`/repositories/${repo.id}`}
          className="card hover:bg-gray-700 transition-colors"
        >
          <div className="flex items-start justify-between">
            <div className="flex items-center">
              <GitBranch className="h-5 w-5 text-blue-500 mr-2" />
              <h3 className="text-lg font-medium text-white">{repo.name}</h3>
            </div>
            <span
              className={clsx(
                'px-2 py-1 text-xs rounded-full',
                repo.is_active
                  ? 'bg-green-900/50 text-green-400'
                  : 'bg-gray-700 text-gray-400'
              )}
            >
              {repo.is_active ? 'Active' : 'Inactive'}
            </span>
          </div>

          {repo.description && (
            <p className="mt-2 text-sm text-gray-400 line-clamp-2">
              {repo.description}
            </p>
          )}

          <div className="mt-4 space-y-2">
            <div className="flex items-center text-sm">
              <span className="text-gray-400 w-24">Branch:</span>
              <span className="text-gray-300">{repo.branch}</span>
            </div>

            {repo.current_jdk_version && (
              <div className="flex items-center text-sm">
                <span className="text-gray-400 w-24">Current JDK:</span>
                <span className="text-gray-300">{repo.current_jdk_version}</span>
              </div>
            )}

            {repo.target_jdk_version && (
              <div className="flex items-center text-sm">
                <span className="text-gray-400 w-24">Target JDK:</span>
                <span className="text-blue-400">{repo.target_jdk_version}</span>
              </div>
            )}
          </div>

          <div className="mt-4 pt-4 border-t border-gray-700 flex items-center justify-between text-sm">
            <div className="flex items-center text-gray-400">
              <Clock className="h-4 w-4 mr-1" />
              {repo.last_analyzed_at
                ? `Analyzed ${new Date(repo.last_analyzed_at).toLocaleDateString()}`
                : 'Not analyzed yet'}
            </div>

            {repo.last_analyzed_at ? (
              <CheckCircle className="h-4 w-4 text-green-500" />
            ) : (
              <AlertTriangle className="h-4 w-4 text-yellow-500" />
            )}
          </div>
        </Link>
      ))}
    </div>
  )
}
