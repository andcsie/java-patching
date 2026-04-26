import { useCallback, useEffect, useRef, useState } from 'react';

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

export interface Trace {
  id: string;
  workflow_id: string;
  status: 'running' | 'completed' | 'failed';
  started_at?: string;
  completed_at?: string;
  total_events: number;
  total_decisions: number;
  total_llm_calls: number;
  total_errors: number;
  total_duration_ms?: number;
}

interface UseTraceOptions {
  maxEvents?: number;
  autoReconnect?: boolean;
  reconnectInterval?: number;
}

interface UseTraceReturn {
  trace: Trace | null;
  events: TraceEvent[];
  connected: boolean;
  error: string | null;
  connect: () => void;
  disconnect: () => void;
}

export function useTrace(
  workflowId: string | null,
  options: UseTraceOptions = {}
): UseTraceReturn {
  const {
    maxEvents = 200,
    autoReconnect = true,
    reconnectInterval = 3000,
  } = options;

  const [trace, setTrace] = useState<Trace | null>(null);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isManuallyDisconnected = useRef(false);

  const connect = useCallback(() => {
    if (!workflowId) return;

    isManuallyDisconnected.current = false;
    setError(null);

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

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
          if (data.trace) {
            setTrace(data.trace);
          }
          setEvents(data.events || []);
        } else if (data.type === 'trace_event') {
          setEvents(prev => {
            const newEvents = [...prev, data.event];
            return newEvents.slice(-maxEvents);
          });
        } else if (data.type === 'trace_complete') {
          setTrace(data.trace);
        } else if (data.type === 'ping') {
          ws.send('pong');
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    ws.onerror = () => {
      setError('Connection error');
      setConnected(false);
    };

    ws.onclose = () => {
      setConnected(false);

      // Auto-reconnect if not manually disconnected
      if (autoReconnect && !isManuallyDisconnected.current && workflowId) {
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, reconnectInterval);
      }
    };
  }, [workflowId, maxEvents, autoReconnect, reconnectInterval]);

  const disconnect = useCallback(() => {
    isManuallyDisconnected.current = true;

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setConnected(false);
  }, []);

  // Connect on mount and when workflowId changes
  useEffect(() => {
    if (workflowId) {
      connect();
    } else {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [workflowId, connect, disconnect]);

  return {
    trace,
    events,
    connected,
    error,
    connect,
    disconnect,
  };
}

export default useTrace;
