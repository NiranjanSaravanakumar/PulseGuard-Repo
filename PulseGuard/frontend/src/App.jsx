import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ComponentRegistry from "./components/ComponentRegistry";
import useWebSocket from "./hooks/useWebSocket";

const BACKEND_HTTP = import.meta.env.VITE_API_URL  || "http://localhost:8000";
const BACKEND_WS   = import.meta.env.VITE_WS_URL   || "ws://localhost:8000/ws";
const MAX_POINTS   = 50;   // rolling history per sensor chart
const MAX_ALERTS   = 100;  // max alerts in memory

export default function App() {
  const [role,       setRole]       = useState("operator");
  const [uiSchema,   setUiSchema]   = useState(null);
  const [alerts,     setAlerts]     = useState([]);
  const [sensorData, setSensorData] = useState({});

  // ── Fetch UI-Schema whenever role changes ─────────────────────────────────
  useEffect(() => {
    setUiSchema(null);
    fetch(`${BACKEND_HTTP}/config?role=${role}`)
      .then((r) => r.json())
      .then(setUiSchema)
      .catch(console.error);
  }, [role]);

  // ── WebSocket message handler ─────────────────────────────────────────────
  const handleMessage = useCallback((msg) => {
    if (msg.type === "alert") {
      setAlerts((prev) =>
        [{ ...msg.data, dismissed: false }, ...prev].slice(0, MAX_ALERTS)
      );
    } else if (msg.type === "sensor_reading") {
      const { sensor_id, value, timestamp } = msg.data;
      setSensorData((prev) => ({
        ...prev,
        [sensor_id]: [
          ...(prev[sensor_id] || []).slice(-(MAX_POINTS - 1)),
          {
            time:  new Date(timestamp * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
            value: parseFloat(value),
          },
        ],
      }));
    }
  }, []);

  const { isConnected } = useWebSocket(`${BACKEND_WS}/${role}`, {
    onMessage: handleMessage,
  });

  const dismissAlert = useCallback((alertId) => {
    setAlerts((prev) =>
      prev.map((a) => (a.alert_id === alertId ? { ...a, dismissed: true } : a))
    );
  }, []);

  // ── Contextual "critical" state ───────────────────────────────────────────
  const hasCritical = alerts.some((a) => a.severity === "CRITICAL" && !a.dismissed);
  const activeCount = alerts.filter((a) => !a.dismissed).length;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-cyan-500/30">
      {/* ── Critical pulsing border overlay ──────────────────────────────── */}
      <AnimatePresence>
        {hasCritical && (
          <motion.div
            key="critical-ring"
            className="fixed inset-0 pointer-events-none z-50 rounded-none border-[3px] border-red-500"
            initial={{ opacity: 0 }}
            animate={{ opacity: [0, 0.9, 0] }}
            transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
          />
        )}
      </AnimatePresence>

      {/* ── Header ───────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 flex items-center justify-between px-6 py-3 bg-slate-900/80 backdrop-blur-md border-b border-slate-800/70">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
            <span className="text-white font-black text-sm tracking-tight">PG</span>
          </div>
          <div>
            <p className="text-base font-bold text-white leading-none">PulseGuard</p>
            <p className="text-[10px] text-slate-400 leading-none mt-0.5 tracking-wide uppercase">
              Industrial Intelligence Platform
            </p>
          </div>
        </div>

        {/* Right controls */}
        <div className="flex items-center gap-3">
          {/* Live / Disconnected badge */}
          <span
            className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full transition-colors ${
              isConnected
                ? "bg-emerald-900/40 text-emerald-400 ring-1 ring-emerald-500/30"
                : "bg-red-900/40 text-red-400 ring-1 ring-red-500/30"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${isConnected ? "bg-emerald-400 animate-pulse" : "bg-red-400"}`}
            />
            {isConnected ? "Live" : "Disconnected"}
          </span>

          {/* Role switcher */}
          <div className="flex bg-slate-800 rounded-xl p-1 gap-1">
            {["operator", "engineer"].map((r) => (
              <button
                key={r}
                onClick={() => setRole(r)}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                  role === r
                    ? "bg-cyan-500 text-white shadow shadow-cyan-500/30"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {r[0].toUpperCase() + r.slice(1)}
              </button>
            ))}
          </div>

          {/* Active alert pill */}
          <AnimatePresence>
            {activeCount > 0 && (
              <motion.span
                key="alert-pill"
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: [1, 1.08, 1], opacity: 1 }}
                exit={{ scale: 0.8, opacity: 0 }}
                transition={{ duration: 0.8, repeat: Infinity, repeatDelay: 1 }}
                className={`text-xs font-bold px-3 py-1.5 rounded-full ${
                  hasCritical
                    ? "bg-red-600 text-white shadow-lg shadow-red-500/30"
                    : "bg-amber-500/20 text-amber-400 ring-1 ring-amber-500/40"
                }`}
              >
                ⚡ {activeCount} Active
              </motion.span>
            )}
          </AnimatePresence>
        </div>
      </header>

      {/* ── Dashboard body ────────────────────────────────────────────────── */}
      <main
        className={`p-5 transition-colors duration-700 ${
          hasCritical ? "bg-red-950/5" : "bg-slate-950"
        }`}
      >
        {uiSchema ? (
          <ComponentRegistry
            schema={uiSchema}
            alerts={alerts}
            sensorData={sensorData}
            onDismiss={dismissAlert}
          />
        ) : (
          <div className="flex items-center justify-center h-72">
            <div className="text-center space-y-3">
              <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin mx-auto" />
              <p className="text-slate-400 text-sm">Loading dashboard schema…</p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
