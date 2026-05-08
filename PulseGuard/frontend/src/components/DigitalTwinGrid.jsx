/**
 * DigitalTwinGrid — 2D factory floor visualization.
 *
 * Receives `pings` map: { sensor_id → { status, value, zone } }
 * Renders 3 zones as glowing node clusters that pulse based on live WS pings.
 * Status colours: ok=emerald, warning=amber, critical=red.
 */
import { motion, AnimatePresence } from "framer-motion";

// ── Zone layout definitions ───────────────────────────────────────────────────
const ZONES = [
  {
    id: "Z1",
    label: "Zone 1 — Furnace Bay",
    description: "High-temp processing",
    col: "col-start-1",
    sensors: [
      { id: "temp_sensor_z1",      label: "TEMP",  icon: "🌡" },
      { id: "pressure_sensor_z1",  label: "PRESS", icon: "⚡" },
      { id: "vibration_sensor_z1", label: "VIB",   icon: "〰" },
      { id: "flow_sensor_z1",      label: "FLOW",  icon: "💧" },
    ],
  },
  {
    id: "Z2",
    label: "Zone 2 — Hydraulics",
    description: "Pressure-critical systems",
    col: "col-start-2",
    sensors: [
      { id: "temp_sensor_z2",      label: "TEMP",  icon: "🌡" },
      { id: "pressure_sensor_z2",  label: "PRESS", icon: "⚡" },
      { id: "vibration_sensor_z2", label: "VIB",   icon: "〰" },
      { id: "flow_sensor_z2",      label: "FLOW",  icon: "💧" },
    ],
  },
  {
    id: "Z3",
    label: "Zone 3 — Cooling Circuit",
    description: "Flow-critical cooling",
    col: "col-start-3",
    sensors: [
      { id: "temp_sensor_z3",      label: "TEMP",  icon: "🌡" },
      { id: "pressure_sensor_z3",  label: "PRESS", icon: "⚡" },
      { id: "vibration_sensor_z3", label: "VIB",   icon: "〰" },
      { id: "flow_sensor_z3",      label: "FLOW",  icon: "💧" },
    ],
  },
];

const STATUS_COLORS = {
  critical: {
    ring:  "border-red-500",
    glow:  "shadow-red-500/60",
    dot:   "bg-red-500",
    text:  "text-red-400",
    bg:    "bg-red-950/40",
  },
  warning: {
    ring:  "border-amber-400",
    glow:  "shadow-amber-400/50",
    dot:   "bg-amber-400",
    text:  "text-amber-400",
    bg:    "bg-amber-950/30",
  },
  ok: {
    ring:  "border-emerald-500/50",
    glow:  "shadow-emerald-500/20",
    dot:   "bg-emerald-500",
    text:  "text-emerald-400",
    bg:    "bg-slate-800/40",
  },
};

function SensorNode({ sensorDef, ping }) {
  const status = ping?.status ?? "ok";
  const colors = STATUS_COLORS[status] ?? STATUS_COLORS.ok;
  const value  = ping?.value;

  return (
    <motion.div
      layout
      className={`
        relative flex flex-col items-center justify-center gap-1
        w-20 h-20 rounded-2xl border backdrop-blur-sm cursor-default
        ${colors.ring} ${colors.bg}
        shadow-lg ${colors.glow}
        transition-colors duration-500
      `}
      animate={
        status === "critical"
          ? { scale: [1, 1.06, 1], borderColor: ["#ef4444", "#fca5a5", "#ef4444"] }
          : status === "warning"
            ? { scale: [1, 1.03, 1] }
            : { scale: 1 }
      }
      transition={{ duration: 1.2, repeat: status !== "ok" ? Infinity : 0, ease: "easeInOut" }}
    >
      {/* Status dot */}
      <span className={`absolute top-2 right-2 w-2 h-2 rounded-full ${colors.dot} ${status !== "ok" ? "animate-pulse" : ""}`} />

      {/* Icon */}
      <span className="text-xl leading-none select-none">{sensorDef.icon}</span>

      {/* Label */}
      <span className={`text-[9px] font-bold tracking-widest ${colors.text}`}>
        {sensorDef.label}
      </span>

      {/* Live value */}
      <AnimatePresence mode="popLayout">
        {value != null && (
          <motion.span
            key={Math.round(value * 10)}
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="text-[10px] font-mono text-slate-300"
          >
            {value.toFixed(1)}
          </motion.span>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function ZonePanel({ zone, pings }) {
  const statuses  = zone.sensors.map((s) => pings[s.id]?.status ?? "ok");
  const zoneStat  = statuses.includes("critical") ? "critical"
                  : statuses.includes("warning")  ? "warning"
                  : "ok";
  const colors    = STATUS_COLORS[zoneStat];

  return (
    <motion.div
      className={`
        flex flex-col gap-3 p-4 rounded-2xl border backdrop-blur-md
        bg-slate-900/50 ${colors.ring}
        shadow-xl ${colors.glow}
        transition-colors duration-700
      `}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      {/* Zone header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-bold text-white tracking-wide">{zone.label}</p>
          <p className="text-[10px] text-slate-500">{zone.description}</p>
        </div>
        <span
          className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${colors.ring} ${colors.text}`}
        >
          {zoneStat.toUpperCase()}
        </span>
      </div>

      {/* Sensor nodes */}
      <div className="grid grid-cols-2 gap-2">
        {zone.sensors.map((s) => (
          <SensorNode key={s.id} sensorDef={s} ping={pings[s.id]} />
        ))}
      </div>
    </motion.div>
  );
}

export default function DigitalTwinGrid({ pings = {} }) {
  const hasData = Object.keys(pings).length > 0;

  return (
    <div className="h-full flex flex-col bg-slate-900/30 rounded-2xl border border-slate-800/60 backdrop-blur-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800/60">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          <span className="text-sm font-bold text-white tracking-wide">Digital Twin</span>
          <span className="text-[10px] text-slate-500 uppercase tracking-widest ml-1">Live Factory Floor</span>
        </div>
        <span className="text-[10px] font-mono text-slate-600">
          {Object.keys(pings).length} / {12} sensors
        </span>
      </div>

      {/* Zone grid */}
      {hasData ? (
        <div className="flex-1 grid grid-cols-1 md:grid-cols-3 gap-4 p-4 overflow-auto">
          {ZONES.map((zone) => (
            <ZonePanel key={zone.id} zone={zone} pings={pings} />
          ))}
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-3">
            <div className="w-8 h-8 border-2 border-cyan-500/50 border-t-cyan-400 rounded-full animate-spin mx-auto" />
            <p className="text-slate-500 text-sm">Waiting for sensor data…</p>
            <p className="text-slate-600 text-xs">Start the simulator to see the factory floor</p>
          </div>
        </div>
      )}
    </div>
  );
}
