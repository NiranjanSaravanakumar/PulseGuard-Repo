/**
 * PulseGuard — API service layer
 * Axios instance + WebSocket factory used by hooks and components.
 */
import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const WS_BASE  = import.meta.env.VITE_WS_URL  || "ws://localhost:8000";

// ── Axios instance ────────────────────────────────────────────────────────────
export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 8000,
  headers: { "Content-Type": "application/json" },
});

// ── REST helpers ──────────────────────────────────────────────────────────────
export const fetchUIConfig = (role = "operator") =>
  api.get(`/api/v1/ui-config?role=${role}`).then((r) => r.data);

export const fetchAlerts = (limit = 50) =>
  api.get(`/api/v1/alerts?limit=${limit}`).then((r) => r.data);

export const acknowledgeAlert = (alertId) =>
  api.patch(`/api/v1/alerts/${alertId}/acknowledge`).then((r) => r.data);

export const fetchZonesHealth = () =>
  api.get("/api/v1/zones/health").then((r) => r.data);

// ── WebSocket factory ─────────────────────────────────────────────────────────
/**
 * Creates a WebSocket connected to /ws/{role}.
 * Returns the raw WebSocket so the caller can call .close().
 *
 * @param {string} role - "operator" | "engineer"
 * @param {{onMessage, onOpen, onClose, onError}} handlers
 */
export function createIndustrialSocket(role, handlers = {}) {
  const { onMessage, onOpen, onClose, onError } = handlers;
  const ws = new WebSocket(`${WS_BASE}/ws/${role}`);

  ws.onopen    = () => onOpen?.();
  ws.onmessage = (e) => {
    try { onMessage?.(JSON.parse(e.data)); } catch { /* ignore malformed frames */ }
  };
  ws.onclose = () => onClose?.();
  ws.onerror = (e) => onError?.(e);

  return ws;
}
