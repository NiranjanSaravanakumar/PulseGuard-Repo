import { motion } from "framer-motion";

function trend(data) {
  if (data.length < 2) return null;
  const d = data[data.length - 1].value - data[data.length - 2].value;
  if (Math.abs(d) < 0.001) return { icon: "→", cls: "text-slate-400" };
  return d > 0
    ? { icon: "↑", cls: "text-orange-400" }
    : { icon: "↓", cls: "text-emerald-400" };
}

export default function StatusCard({ config, data }) {
  const latest = data[data.length - 1]?.value;
  const t      = trend(data);
  // Simple percentage bar (assumes max ≈ 200 for most process values)
  const pct    = latest != null ? Math.min((latest / 200) * 100, 100) : 0;

  return (
    <motion.div
      className="h-full bg-slate-900 rounded-2xl border border-slate-800 flex flex-col items-center justify-center p-5 text-center"
      initial={{ opacity: 0, scale: 0.94 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
    >
      <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-2">
        {config.title}
      </p>

      <div className="flex items-end gap-1.5">
        <motion.p
          key={latest}
          initial={{ scale: 1.15, opacity: 0 }}
          animate={{ scale: 1,    opacity: 1 }}
          className="text-4xl font-black text-white tabular-nums"
        >
          {latest != null ? latest.toFixed(2) : "—"}
        </motion.p>
        {t && (
          <span className={`text-xl font-bold mb-1 ${t.cls}`}>{t.icon}</span>
        )}
      </div>

      <p className="text-[10px] text-slate-600 mt-1">{config.sensor}</p>

      {/* Mini progress bar */}
      <div className="mt-4 w-full bg-slate-800 rounded-full h-1">
        <motion.div
          className="h-1 rounded-full bg-gradient-to-r from-cyan-500 to-blue-600"
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
      </div>
    </motion.div>
  );
}
