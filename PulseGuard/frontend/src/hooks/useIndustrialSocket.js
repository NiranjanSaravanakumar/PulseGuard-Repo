/**
 * useIndustrialSocket — custom WebSocket hook with auto-reconnect.
 *
 * Returns { status } where status is one of:
 *   "connecting" | "connected" | "disconnected"
 *
 * The green/red connection dot in the header reads from this status.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { createIndustrialSocket } from "../services/api";

const RECONNECT_DELAY_MS = 3000;

export default function useIndustrialSocket(role, { onMessage } = {}) {
  const [status, setStatus]   = useState("connecting");
  const wsRef                 = useRef(null);
  const retryTimer            = useRef(null);
  const unmounted             = useRef(false);

  const connect = useCallback(() => {
    if (unmounted.current) return;
    setStatus("connecting");

    wsRef.current = createIndustrialSocket(role, {
      onOpen: () => {
        if (!unmounted.current) setStatus("connected");
      },
      onMessage: (msg) => {
        if (!unmounted.current) onMessage?.(msg);
      },
      onClose: () => {
        if (unmounted.current) return;
        setStatus("disconnected");
        retryTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
      },
      onError: () => {
        // close triggers onClose → retry logic
        wsRef.current?.close();
      },
    });
  }, [role, onMessage]);

  useEffect(() => {
    unmounted.current = false;
    connect();
    return () => {
      unmounted.current = true;
      clearTimeout(retryTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { status };
}
