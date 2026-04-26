import { useState } from 'react'
import { ChevronDown, ChevronRight, Copy, Check, FileCode } from 'lucide-react'

interface PatchData {
  file_path: string
  impacts_count: number
  patch: {
    unified_diff?: string
    changes_summary?: string[]
    warnings?: string[]
    error?: string
  }
}

interface DiffViewerProps {
  patches: PatchData[]
}

function DiffLine({ line, index }: { line: string; index: number }) {
  let bgClass = 'bg-gray-900'
  let textClass = 'text-gray-300'

  if (line.startsWith('+++') || line.startsWith('---')) {
    bgClass = 'bg-gray-800'
    textClass = 'text-gray-400 font-bold'
  } else if (line.startsWith('@@')) {
    bgClass = 'bg-blue-900/30'
    textClass = 'text-blue-400'
  } else if (line.startsWith('+')) {
    bgClass = 'bg-green-900/40'
    textClass = 'text-green-300'
  } else if (line.startsWith('-')) {
    bgClass = 'bg-red-900/40'
    textClass = 'text-red-300'
  }

  return (
    <div className={`${bgClass} flex font-mono text-xs`}>
      <span className="w-8 text-right pr-2 text-gray-600 select-none border-r border-gray-700">
        {index + 1}
      </span>
      <span className={`pl-2 whitespace-pre ${textClass}`}>{line || ' '}</span>
    </div>
  )
}

function FileDiff({ patch }: { patch: PatchData }) {
  const [expanded, setExpanded] = useState(true)
  const [copied, setCopied] = useState(false)

  const fileName = patch.file_path.split('/').pop() || patch.file_path
  const hasError = !!patch.patch.error
  const hasDiff = !!patch.patch.unified_diff

  const copyDiff = () => {
    if (patch.patch.unified_diff) {
      navigator.clipboard.writeText(patch.patch.unified_diff)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="border border-gray-700 rounded-lg overflow-hidden">
      {/* File Header */}
      <div
        className={`flex items-center justify-between p-3 cursor-pointer ${
          hasError ? 'bg-red-900/20' : hasDiff ? 'bg-gray-800' : 'bg-yellow-900/20'
        }`}
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-gray-400 mr-2" />
          ) : (
            <ChevronRight className="h-4 w-4 text-gray-400 mr-2" />
          )}
          <FileCode className="h-4 w-4 text-blue-400 mr-2" />
          <span className="text-white font-medium">{fileName}</span>
          <span className="ml-2 text-xs text-gray-500">{patch.file_path}</span>
        </div>
        <div className="flex items-center space-x-3">
          <span className="text-xs text-gray-400">{patch.impacts_count} impacts</span>
          {hasError ? (
            <span className="text-xs text-red-400 bg-red-900/30 px-2 py-0.5 rounded">Error</span>
          ) : hasDiff ? (
            <span className="text-xs text-green-400 bg-green-900/30 px-2 py-0.5 rounded">Ready</span>
          ) : (
            <span className="text-xs text-yellow-400 bg-yellow-900/30 px-2 py-0.5 rounded">No changes</span>
          )}
          {hasDiff && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                copyDiff()
              }}
              className="p-1 hover:bg-gray-700 rounded"
              title="Copy diff"
            >
              {copied ? (
                <Check className="h-4 w-4 text-green-400" />
              ) : (
                <Copy className="h-4 w-4 text-gray-400" />
              )}
            </button>
          )}
        </div>
      </div>

      {/* Diff Content */}
      {expanded && (
        <div className="bg-gray-900">
          {hasError && (
            <div className="p-3 text-red-400 text-sm bg-red-900/10">
              {patch.patch.error}
            </div>
          )}

          {patch.patch.warnings && patch.patch.warnings.length > 0 && (
            <div className="p-3 border-b border-gray-700">
              {patch.patch.warnings.map((w, i) => (
                <p key={i} className="text-yellow-400 text-xs">
                  Warning: {w}
                </p>
              ))}
            </div>
          )}

          {patch.patch.changes_summary && patch.patch.changes_summary.length > 0 && (
            <div className="p-3 bg-gray-800/50 border-b border-gray-700">
              <p className="text-xs text-gray-400 mb-1">Changes:</p>
              <ul className="text-xs text-gray-300 space-y-0.5">
                {patch.patch.changes_summary.map((s, i) => (
                  <li key={i}>• {s}</li>
                ))}
              </ul>
            </div>
          )}

          {hasDiff ? (
            <div className="overflow-x-auto">
              {patch.patch.unified_diff!.split('\n').map((line, i) => (
                <DiffLine key={i} line={line} index={i} />
              ))}
            </div>
          ) : !hasError && (
            <div className="p-4 text-gray-500 text-sm text-center">
              No diff generated. The fixes may not have applied cleanly.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function DiffViewer({ patches }: DiffViewerProps) {
  if (!patches || patches.length === 0) {
    return (
      <div className="text-gray-400 text-center py-4">
        No patches to display
      </div>
    )
  }

  const successfulPatches = patches.filter(p => p.patch.unified_diff && !p.patch.error)
  const failedPatches = patches.filter(p => p.patch.error)

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center space-x-4">
          <span className="text-gray-300">
            {patches.length} file{patches.length !== 1 ? 's' : ''}
          </span>
          {successfulPatches.length > 0 && (
            <span className="text-green-400">
              {successfulPatches.length} with changes
            </span>
          )}
          {failedPatches.length > 0 && (
            <span className="text-red-400">
              {failedPatches.length} failed
            </span>
          )}
        </div>
        {successfulPatches.length > 0 && (
          <button
            onClick={() => {
              const allDiffs = successfulPatches
                .map(p => `# ${p.file_path}\n${p.patch.unified_diff}`)
                .join('\n\n')
              navigator.clipboard.writeText(allDiffs)
            }}
            className="text-xs text-blue-400 hover:text-blue-300 flex items-center"
          >
            <Copy className="h-3 w-3 mr-1" />
            Copy all
          </button>
        )}
      </div>

      {/* File Diffs */}
      <div className="space-y-3">
        {patches.map((patch, i) => (
          <FileDiff key={i} patch={patch} />
        ))}
      </div>
    </div>
  )
}
