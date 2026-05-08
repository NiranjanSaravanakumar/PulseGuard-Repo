import { motion, AnimatePresence } from "framer-motion";

// ── Per-severity visual tokens ────────────────────────────────────────────────
const SEV = {
  CRITICAL: {
    ring:   "border-red-500/50",
    bg:     "bg-red-950/40",
    badge:  "bg-red-600 text-white",
    dot:    "bg-red-500 animate-pulse",
    bar:    "#ef4444",
  },
  WARNING: {
    ring:   "border-amber-500/40",
    bg:     "bg-amber-950/30",
    badge:  "bg-amber-500 text-black",
    dot:    "bg-amber-400",
    bar:    "#f59e0b",
  },
  INFO: {
    ring:   "border-blue-500/30",
    bg:     "bg-blue-950/20",
    badge:  "bg-blue-600 text-white",
    dot:    "bg-blue-400",
    bar:    "#3b82f6",
  },
  PREDICTION: {
    ring:   "border-violet-500/50",
    bg:     "bg-violet-950/30",
    badge:  "bg-violet-600 text-white",
    dot:    "bg-violet-400 animate-pulse",
    bar:    "#8b5cf6",
  },
  ZONE_ALARM: {
    ring:   "border-rose-500/70",
    bg:     "bg-rose-950/50",
    badge:  "bg-rose-700 text-white",
    dot:    "bg-rose-400 animate-ping",
    bar:    "#f43f5e",
  },
};

// ── Single alert card (Team-style) ────────────────────────────────────────────
function AlertCard({ alert, onDismiss }) {
  const sev = SEV[alert.severity] ?? SEV.INFO;
  const ts  = alert.created_at
    ? new Date(alert.created_at).toLocaleTimeString()
    : new Date((alert.timestamp ?? 0) * 1000).toLocaleTimeString();

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 30 }}
      animate={{ opacity: 1, x: 0  }}
      exit={{ opacity: 0, x: -30, height: 0, marginBottom: 0, paddingTop: 0, paddingBottom: 0 }}
      transition={{ duration: 0.28 }}
      className={`relative rounded-xl border p-4 overflow-hidden ${sev.ring} ${sev.bg}`}
    >
      {/* Criticality score bar along the bottom */}
      <div
        className="absolute bottom-0 left-0 h-[2px] rounded-full"
        style={{ width: `${alert.criticality_score ?? 0}%`, background: sev.bar }}
      />

      <div className="flex items-start gap-3">
        {/* Status dot */}
        <span className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${sev.dot}`} />

        {/* Body */}
        <div className="flex-1 min-w-0">
          {/* Meta row */}
          <div className="flex flex-wrap items-center gap-1.5 mb-1.5">
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${sev.badge}`}>
              {alert.is_aggregated ? "AI AGGREGATED" : alert.severity}
            </span>
            <span className="text-xs text-slate-400 truncate">{alert.sensor_id}</span>
            <span className="text-slate-700 text-xs">·</span>
            <span className="text-xs text-slate-500">{alert.sector}</span>
          </div>

          {/* Message */}
          <p className="text-sm text-slate-200 font-medium leading-snug">
            {alert.zone_summary || alert.summary || alert.message}
          </p>

          {alert.is_prediction && alert.eta_seconds != null && (
            <p className="text-xs text-violet-400 mt-1 font-mono">
              ⏱ Breach in ~{alert.eta_seconds.toFixed(0)}s @ +{alert.velocity?.toFixed(3)}/s
            </p>
          )}
          {alert.is_zone_alarm && alert.affected_sensors?.length > 0 && (
            <p className="text-xs text-rose-300 mt-1">
              Sensors: {alert.affected_sensors.join(", ")}
            </p>
          )}
        </div>

        {/* Right column */}
        <div className="flex flex-col items-end gap-1.5 shrink-0 ml-2">
          <span className="text-[10px] text-slate-500">{ts}</span>
          <span
            className={`text-sm font-black tabular-nums ${
              (alert.criticality_score ?? 0) >= 75 ? "text-red-400" : "text-amber-400"
            }`}
          >
            {(alert.criticality_score ?? 0).toFixed(1)}
            <span className="text-[9px] font-normal text-slate-600 ml-0.5">/100</span>
          </span>
          <button
            onClick={() => onDismiss?.(alert.alert_id)}
            className="text-[10px] text-slate-600 hover:text-slate-300 transition-colors px-2 py-0.5 rounded hover:bg-slate-800"
          >
            Dismiss
          </button>
        </div>
      </div>
    </motion.div>
  );
}

// ── Intelligence Feed panel ───────────────────────────────────────────────────
export default function AlertFeed({ label, alerts, onDismiss }) {
  const active = (alerts ?? []).filter((a) => !a.dismissed).slice(0, 25);

  return (
    <div className="h-full bg-slate-900/50 backdrop-blur-md rounded-2xl border border-slate-700/50 shadow-lg shadow-black/30 flex flex-col overflow-hidden">
      {/* Panel header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800/60 shrink-0">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          <h3 className="text-sm font-semibold text-white">{label || "Intelligence Feed"}</h3>
        </div>
        <span className="text-xs text-slate-500 tabular-nums">{active.length} active</span>
      </div>

      {/* Scrollable feed */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 pulseguard-scroll">
        {active.length === 0 ? (
          <div className="h-full flex items-center justify-center py-12">
            <div className="text-center">
              <div className="text-4xl mb-3">✓</div>
              <p className="text-emerald-400 text-sm font-semibold">All Clear</p>
              <p className="text-slate-600 text-xs mt-1">No active alerts detected</p>
            </div>
          </div>
        ) : (
          <AnimatePresence mode="popLayout">
            {active.map((alert) => (
              <AlertCard key={alert.alert_id} alert={alert} onDismiss={onDismiss} />
            ))}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
