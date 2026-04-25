import clsx from 'clsx'

interface Props {
  level?: string
  score?: number
  showScore?: boolean
}

const config: Record<string, { bg: string; text: string; label: string }> = {
  critical: {
    bg: 'bg-red-900/50',
    text: 'text-red-400',
    label: 'Critical',
  },
  high: {
    bg: 'bg-orange-900/50',
    text: 'text-orange-400',
    label: 'High',
  },
  medium: {
    bg: 'bg-yellow-900/50',
    text: 'text-yellow-400',
    label: 'Medium',
  },
  low: {
    bg: 'bg-green-900/50',
    text: 'text-green-400',
    label: 'Low',
  },
}

export default function RiskBadge({ level, score, showScore = true }: Props) {
  if (!level) return null

  const levelConfig = config[level] || config.low

  return (
    <span
      className={clsx(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-sm font-medium',
        levelConfig.bg,
        levelConfig.text
      )}
    >
      {levelConfig.label}
      {showScore && score !== undefined && (
        <span className="ml-1.5 text-xs opacity-75">({score})</span>
      )}
    </span>
  )
}
