import { CheckCircle, Circle, Clock, Loader2, XCircle } from 'lucide-react';

export interface TraceStep {
  id: string;
  name: string;
  agent: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  startedAt?: string;
  completedAt?: string;
  duration_ms?: number;
  events_count?: number;
  llm_calls?: number;
  errors?: number;
}

interface TraceTimelineProps {
  steps: TraceStep[];
  currentStep?: string;
}

export function TraceTimeline({ steps, currentStep }: TraceTimelineProps) {
  const getStatusIcon = (status: TraceStep['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'running':
        return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />;
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-500" />;
      default:
        return <Circle className="w-5 h-5 text-gray-300" />;
    }
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-4">
      <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <Clock className="w-5 h-5 text-gray-600" />
        Workflow Timeline
      </h3>

      <div className="relative">
        {steps.map((step, index) => (
          <div key={step.id} className="flex items-start mb-4 last:mb-0">
            {/* Timeline Line */}
            {index < steps.length - 1 && (
              <div
                className={`
                  absolute left-[9px] w-0.5 h-full mt-5
                  ${step.status === 'completed' ? 'bg-green-500' :
                    step.status === 'running' ? 'bg-blue-500' :
                    'bg-gray-200'}
                `}
                style={{ height: '100%' }}
              />
            )}

            {/* Status Icon */}
            <div className="relative z-10 bg-white">
              {getStatusIcon(step.status)}
            </div>

            {/* Content */}
            <div className="ml-4 flex-1">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className={`font-medium ${
                    step.status === 'running' ? 'text-blue-700' :
                    step.status === 'completed' ? 'text-green-700' :
                    step.status === 'failed' ? 'text-red-700' :
                    'text-gray-500'
                  }`}>
                    {step.name}
                  </h4>
                  <p className="text-xs text-gray-500">
                    Agent: {step.agent}
                  </p>
                </div>

                {step.duration_ms && (
                  <span className="text-sm text-gray-500">
                    {formatDuration(step.duration_ms)}
                  </span>
                )}
              </div>

              {/* Stats */}
              {(step.events_count || step.llm_calls || step.errors) && (
                <div className="flex gap-4 mt-1 text-xs text-gray-400">
                  {step.events_count !== undefined && (
                    <span>{step.events_count} events</span>
                  )}
                  {step.llm_calls !== undefined && (
                    <span>{step.llm_calls} LLM calls</span>
                  )}
                  {step.errors !== undefined && step.errors > 0 && (
                    <span className="text-red-500">{step.errors} errors</span>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default TraceTimeline;
