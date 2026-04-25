import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, FileText, AlertTriangle, Download } from 'lucide-react'
import { useAnalysis } from '../../hooks/useAnalysis'
import ReactMarkdown from 'react-markdown'
import RiskBadge from './RiskBadge'
import ImpactList from './ImpactList'

export default function AnalysisView() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: analysis, isLoading } = useAnalysis(id!)

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  if (!analysis) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-400">Analysis not found</p>
      </div>
    )
  }

  const isRunning = analysis.status === 'pending' || analysis.status === 'running'

  return (
    <div>
      <button
        onClick={() => navigate(-1)}
        className="flex items-center text-gray-400 hover:text-white mb-4"
      >
        <ArrowLeft className="h-4 w-4 mr-2" />
        Back
      </button>

      {/* Header */}
      <div className="card mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">
              Analysis: {analysis.from_version} → {analysis.to_version}
            </h1>
            <p className="text-gray-400 mt-1">
              Created {new Date(analysis.created_at).toLocaleString()}
            </p>
          </div>

          <div className="flex items-center space-x-3">
            <RiskBadge level={analysis.risk_level} score={analysis.risk_score} />
            <span
              className={`px-3 py-1 rounded-full text-sm ${
                analysis.status === 'completed'
                  ? 'bg-green-900/50 text-green-400'
                  : analysis.status === 'running'
                  ? 'bg-blue-900/50 text-blue-400 animate-pulse'
                  : analysis.status === 'failed'
                  ? 'bg-red-900/50 text-red-400'
                  : 'bg-gray-600 text-gray-300'
              }`}
            >
              {isRunning ? 'Analyzing...' : analysis.status}
            </span>
          </div>
        </div>

        {analysis.error_message && (
          <div className="mt-4 bg-red-900/30 border border-red-500/50 rounded-md p-4 flex items-start">
            <AlertTriangle className="h-5 w-5 text-red-500 mr-2 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-red-200 font-medium">Analysis Failed</p>
              <p className="text-red-300 text-sm mt-1">{analysis.error_message}</p>
            </div>
          </div>
        )}

        {/* Stats */}
        <div className="mt-6 grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-gray-700 rounded-lg p-4">
            <span className="text-gray-400 text-sm">Total Files</span>
            <p className="text-2xl font-bold text-white">{analysis.total_files_analyzed}</p>
          </div>
          <div className="bg-gray-700 rounded-lg p-4">
            <span className="text-gray-400 text-sm">Total Impacts</span>
            <p className="text-2xl font-bold text-white">{analysis.impacts?.length || 0}</p>
          </div>
          <div className="bg-gray-700 rounded-lg p-4">
            <span className="text-gray-400 text-sm">Critical/High</span>
            <p className="text-2xl font-bold text-red-400">
              {analysis.impacts?.filter((i: any) =>
                ['critical', 'high'].includes(i.severity)
              ).length || 0}
            </p>
          </div>
          <div className="bg-gray-700 rounded-lg p-4">
            <span className="text-gray-400 text-sm">Medium</span>
            <p className="text-2xl font-bold text-yellow-400">
              {analysis.impacts?.filter((i: any) => i.severity === 'medium').length || 0}
            </p>
          </div>
          <div className="bg-gray-700 rounded-lg p-4">
            <span className="text-gray-400 text-sm">Low</span>
            <p className="text-2xl font-bold text-green-400">
              {analysis.impacts?.filter((i: any) => i.severity === 'low').length || 0}
            </p>
          </div>
        </div>
      </div>

      {/* Summary */}
      {analysis.summary && (
        <div className="card mb-6">
          <div className="flex items-center mb-4">
            <FileText className="h-5 w-5 text-blue-500 mr-2" />
            <h2 className="text-lg font-medium text-white">Summary</h2>
          </div>
          <p className="text-gray-300">{analysis.summary}</p>
        </div>
      )}

      {/* Migration Plan */}
      {analysis.suggestions?.migration_plan && (
        <div className="card mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium text-white">Migration Plan</h2>
            <button className="btn btn-secondary flex items-center text-sm">
              <Download className="h-4 w-4 mr-2" />
              Export
            </button>
          </div>
          <div className="prose prose-invert max-w-none">
            <ReactMarkdown>{analysis.suggestions.migration_plan}</ReactMarkdown>
          </div>
        </div>
      )}

      {/* Impact List */}
      {analysis.impacts && analysis.impacts.length > 0 && (
        <div className="card">
          <h2 className="text-lg font-medium text-white mb-4">
            Impacts ({analysis.impacts.length})
          </h2>
          <ImpactList impacts={analysis.impacts} />
        </div>
      )}

      {isRunning && (
        <div className="card mt-6 text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-400">
            Analysis in progress. This page will auto-refresh.
          </p>
        </div>
      )}
    </div>
  )
}
