import { useState, useEffect, useRef, useCallback } from "react";

/**
 * Auto-reconnecting WebSocket hook.
 * @param {string} url  - Full WS URL
 * @param {{ onMessage: (data: object) => void }} opts
 */
export default function useWebSocket(url, { onMessage } = {}) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef           = useRef(null);
  const timerRef        = useRef(null);
  const onMessageRef    = useRef(onMessage);
  onMessageRef.current  = onMessage;   // always latest without re-subscribing

  const connect = useCallback(() => {
    // Prevent double-connect
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      clearTimeout(timerRef.current);
    };

    ws.onmessage = ({ data }) => {
      try {
        onMessageRef.current?.(JSON.parse(data));
      } catch {
        // non-JSON frame — ignore
      }
    };

    ws.onerror = () => {
      // onerror always precedes onclose; just let onclose handle reconnect
    };

    ws.onclose = () => {
      setIsConnected(false);
      timerRef.current = setTimeout(connect, 3000);
    };
  }, [url]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(timerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return { isConnected, send };
}
