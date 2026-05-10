import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import DynamicGrid           from "./components/DynamicGrid";
import CommandPalette        from "./components/CommandPalette";
import ZoneSummaryBar        from "./components/ZoneSummaryBar";
import useIndustrialSocket   from "./hooks/useIndustrialSocket";
import useVoiceAlerts        from "./hooks/useVoiceAlerts";
import { fetchUIConfig, api } from "./services/api";

const MAX_POINTS = 60;   // rolling chart history per sensor
const MAX_ALERTS = 150;  // max alerts kept in memory

const ROLES = ["operator", "engineer", "admin"];

export default function App() {
  const [role,       setRole]       = useState("operator");
  const [uiSchema,   setUiSchema]   = useState(null);
  const [alerts,     setAlerts]     = useState([]);
  const [sensorData, setSensorData] = useState({});
  const [sensorPings, setSensorPings] = useState({});  // for Digital Twin
  const [paletteOpen, setPaletteOpen] = useState(false);

  // ── Fetch UI-Schema whenever role changes ─────────────────────────────────
  useEffect(() => {
    setUiSchema(null);
    fetchUIConfig(role)
      .then(setUiSchema)
      .catch(console.error);
  }, [role]);

  // ── Ctrl+K — Command Palette ──────────────────────────────────────────────
  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

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
            time:  new Date(timestamp).toLocaleTimeString([], {
              hour: "2-digit", minute: "2-digit", second: "2-digit",
            }),
            value: parseFloat(value),
          },
        ],
      }));
    } else if (msg.type === "sensor_ping") {
      const { sensor_id, status, value, zone } = msg.data;
      setSensorPings((prev) => ({ ...prev, [sensor_id]: { status, value, zone } }));
    }
  }, []);

  const { status } = useIndustrialSocket(role, { onMessage: handleMessage });
  const isConnected = status === "connected";

  // ── Voice alerts ──────────────────────────────────────────────────────────
  useVoiceAlerts(alerts);

  const dismissAlert = useCallback((alertId) => {
    // Optimistic UI update
    setAlerts((prev) =>
      prev.map((a) => (a.alert_id === alertId ? { ...a, dismissed: true } : a))
    );
    // Persist acknowledgement to backend
    api.patch(`/api/v1/alerts/${alertId}/acknowledge`).catch(() => {/* non-critical */});
  }, []);

  // ── Contextual "critical" state ───────────────────────────────────────────
  const hasCritical = alerts.some((a) => a.severity === "CRITICAL" && !a.dismissed);
  const activeCount = alerts.filter((a) => !a.dismissed).length;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-cyan-500/30">
      {/* ── Command Palette ───────────────────────────────────────────────── */}
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        currentRole={role}
        onRoleChange={(r) => { setRole(r); setSensorData({}); }}
      />

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
              Digital Twin Command Center
            </p>
          </div>
        </div>

        {/* Zone health pills */}
        <ZoneSummaryBar sensorPings={sensorPings} />

        {/* Right controls */}
        <div className="flex items-center gap-3">
          {/* Live / Disconnected badge */}
          <span
            className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full transition-colors ${
              isConnected
                ? "bg-emerald-900/40 text-emerald-400 ring-1 ring-emerald-500/30"
                : status === "connecting"
                  ? "bg-yellow-900/40 text-yellow-400 ring-1 ring-yellow-500/30"
                  : "bg-red-900/40 text-red-400 ring-1 ring-red-500/30"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isConnected
                  ? "bg-emerald-400 animate-pulse"
                  : status === "connecting"
                    ? "bg-yellow-400 animate-pulse"
                    : "bg-red-400"
              }`}
            />
            {isConnected ? "Live" : status === "connecting" ? "Connecting…" : "Disconnected"}
          </span>

          {/* Role switcher */}
          <div className="flex bg-slate-800/60 backdrop-blur-sm rounded-xl p-1 gap-1">
            {ROLES.map((r) => (
              <button
                key={r}
                onClick={() => { setRole(r); setSensorData({}); }}
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

          {/* Ctrl+K hint */}
          <button
            onClick={() => setPaletteOpen(true)}
            className="hidden sm:flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors px-3 py-1.5 rounded-lg border border-slate-800 hover:border-slate-700"
          >
            <kbd className="font-mono text-[10px]">Ctrl+K</kbd>
            <span>Command</span>
          </button>

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
          <DynamicGrid
            schema={uiSchema}
            alerts={alerts}
            sensorData={sensorData}
            sensorPings={sensorPings}
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
