import { useEffect, useRef, useState } from 'react';
import { Activity, AlertCircle, Bot, CheckCircle, Clock, Cpu, Lightbulb, Zap } from 'lucide-react';

export interface TraceEvent {
  id: string;
  trace_id: string;
  agent: string;
  event_type: 'info' | 'action' | 'decision' | 'llm_call' | 'error' | 'warning';
  message: string;
  data?: Record<string, unknown>;
  timestamp: string;
  duration_ms?: number;
  llm_provider?: string;
  tokens_in?: number;
  tokens_out?: number;
  decision?: string;
  reason?: string;
  confidence?: number;
}

interface ActivityFeedProps {
  workflowId: string;
  maxEvents?: number;
  autoScroll?: boolean;
}

const EVENT_ICONS: Record<string, React.ReactNode> = {
  info: <Activity className="w-4 h-4 text-blue-500" />,
  action: <Zap className="w-4 h-4 text-yellow-500" />,
  decision: <Lightbulb className="w-4 h-4 text-purple-500" />,
  llm_call: <Cpu className="w-4 h-4 text-green-500" />,
  error: <AlertCircle className="w-4 h-4 text-red-500" />,
  warning: <AlertCircle className="w-4 h-4 text-orange-500" />,
};

const AGENT_COLORS: Record<string, string> = {
  analyzer: 'bg-blue-100 text-blue-800',
  fixer: 'bg-green-100 text-green-800',
  patcher: 'bg-purple-100 text-purple-800',
  orchestrator: 'bg-yellow-100 text-yellow-800',
  renovate: 'bg-orange-100 text-orange-800',
  openrewrite: 'bg-pink-100 text-pink-800',
};

export function ActivityFeed({ workflowId, maxEvents = 100, autoScroll = true }: ActivityFeedProps) {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const feedRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!workflowId) return;

    // Use relative URL to go through Vite proxy in dev, or same origin in prod
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/api/traces/ws/${workflowId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setError(null);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'initial_state') {
          setEvents(data.events || []);
        } else if (data.type === 'trace_event') {
          setEvents(prev => {
            const newEvents = [...prev, data.event];
            return newEvents.slice(-maxEvents);
          });
        } else if (data.type === 'ping') {
          ws.send('pong');
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    ws.onerror = () => {
      setError('WebSocket connection error');
      setConnected(false);
    };

    ws.onclose = () => {
      setConnected(false);
    };

    return () => {
      ws.close();
    };
  }, [workflowId, maxEvents]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [events, autoScroll]);

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
  };

  const getAgentColor = (agent: string) => {
    return AGENT_COLORS[agent.toLowerCase()] || 'bg-gray-100 text-gray-800';
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <Bot className="w-5 h-5 text-gray-600" />
          <h3 className="font-semibold text-gray-900">Agent Activity</h3>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-gray-400'}`} />
          <span className="text-xs text-gray-500">
            {connected ? 'Live' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="px-4 py-2 bg-red-50 text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Events Feed */}
      <div
        ref={feedRef}
        className="flex-1 overflow-y-auto p-2 space-y-1 max-h-96"
      >
        {events.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            <Activity className="w-8 h-8 mx-auto mb-2 text-gray-400" />
            <p className="text-sm">No activity yet</p>
            <p className="text-xs text-gray-400">Events will appear here as agents work</p>
          </div>
        ) : (
          events.map((event) => (
            <EventRow key={event.id} event={event} formatTime={formatTime} getAgentColor={getAgentColor} />
          ))
        )}
      </div>

      {/* Footer Stats */}
      <div className="px-4 py-2 border-t border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>{events.length} events</span>
          <span>
            {events.filter(e => e.event_type === 'llm_call').length} LLM calls
          </span>
          <span>
            {events.filter(e => e.event_type === 'error').length} errors
          </span>
        </div>
      </div>
    </div>
  );
}

interface EventRowProps {
  event: TraceEvent;
  formatTime: (timestamp: string) => string;
  getAgentColor: (agent: string) => string;
}

function EventRow({ event, formatTime, getAgentColor }: EventRowProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={`
        px-3 py-2 rounded-md text-sm cursor-pointer transition-colors
        ${event.event_type === 'error' ? 'bg-red-50 hover:bg-red-100' :
          event.event_type === 'warning' ? 'bg-yellow-50 hover:bg-yellow-100' :
          'bg-gray-50 hover:bg-gray-100'}
      `}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-start gap-2">
        {/* Icon */}
        <div className="mt-0.5">
          {EVENT_ICONS[event.event_type] || EVENT_ICONS.info}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {/* Timestamp */}
            <span className="text-xs text-gray-400 font-mono">
              {formatTime(event.timestamp)}
            </span>

            {/* Agent Badge */}
            <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${getAgentColor(event.agent)}`}>
              {event.agent}
            </span>

            {/* Duration */}
            {event.duration_ms && (
              <span className="flex items-center gap-1 text-xs text-gray-400">
                <Clock className="w-3 h-3" />
                {event.duration_ms}ms
              </span>
            )}

            {/* LLM Stats */}
            {event.event_type === 'llm_call' && (
              <span className="text-xs text-gray-400">
                {event.llm_provider} ({event.tokens_in}+{event.tokens_out} tokens)
              </span>
            )}

            {/* Confidence */}
            {event.confidence !== undefined && (
              <span className={`text-xs px-1.5 py-0.5 rounded ${
                event.confidence >= 80 ? 'bg-green-100 text-green-700' :
                event.confidence >= 50 ? 'bg-yellow-100 text-yellow-700' :
                'bg-red-100 text-red-700'
              }`}>
                {event.confidence}% conf
              </span>
            )}
          </div>

          {/* Message */}
          <p className="text-gray-700 mt-1 truncate">
            {event.message}
          </p>

          {/* Decision Details */}
          {event.event_type === 'decision' && event.reason && (
            <p className="text-xs text-gray-500 mt-1 italic">
              Reason: {event.reason}
            </p>
          )}

          {/* Expanded Details */}
          {expanded && event.data && Object.keys(event.data).length > 0 && (
            <pre className="mt-2 p-2 bg-gray-800 text-gray-100 rounded text-xs overflow-x-auto">
              {JSON.stringify(event.data, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

export default ActivityFeed;
