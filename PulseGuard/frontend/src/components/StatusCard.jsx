import { motion } from "framer-motion";

function trend(data) {
  if (data.length < 2) return null;
  const d = data[data.length - 1].value - data[data.length - 2].value;
  if (Math.abs(d) < 0.001) return { icon: "→", cls: "text-slate-400" };
  return d > 0
    ? { icon: "↑", cls: "text-orange-400" }
    : { icon: "↓", cls: "text-emerald-400" };
}

export default function StatusCard({ sensorId, label, value, readings = [] }) {
  const t   = trend(readings);
  const pct = value != null ? Math.min((value / 200) * 100, 100) : 0;

  // Neon status colour based on value vs expected max
  const pctNorm = value != null ? value / 200 : 0;
  const neon    = pctNorm > 0.85 ? "text-red-400 drop-shadow-[0_0_6px_rgba(239,68,68,0.8)]"
               : pctNorm > 0.65 ? "text-amber-400 drop-shadow-[0_0_6px_rgba(251,191,36,0.7)]"
               : "text-cyan-400 drop-shadow-[0_0_6px_rgba(34,211,238,0.7)]";

  const barColor = pctNorm > 0.85 ? "from-red-600 to-red-400"
                 : pctNorm > 0.65 ? "from-amber-500 to-amber-300"
                 : "from-cyan-600 to-cyan-400";

  return (
    <motion.div
      className="h-full bg-slate-900/50 backdrop-blur-md rounded-2xl border border-slate-700/50 shadow-lg shadow-black/30 flex flex-col items-center justify-center p-5 text-center"
      initial={{ opacity: 0, scale: 0.94 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
    >
      <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-2">
        {label}
      </p>

      <div className="flex items-end gap-1.5">
        <motion.p
          key={value}
          initial={{ scale: 1.15, opacity: 0 }}
          animate={{ scale: 1,    opacity: 1 }}
          className={`text-4xl font-black tabular-nums ${neon}`}
        >
          {value != null ? value.toFixed(2) : "—"}
        </motion.p>
        {t && (
          <span className={`text-xl font-bold mb-1 ${t.cls}`}>{t.icon}</span>
        )}
      </div>

      <p className="text-[10px] text-slate-600 mt-1 font-mono">{sensorId}</p>

      {/* Neon progress bar */}
      <div className="mt-4 w-full bg-slate-800 rounded-full h-1">
        <motion.div
          className={`h-1 rounded-full bg-gradient-to-r ${barColor}`}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          style={{ filter: "drop-shadow(0 0 4px currentColor)" }}
        />
      </div>
    </motion.div>
  );
}
