import { motion } from "framer-motion";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm shadow-xl">
      <p className="font-bold text-cyan-400">{payload[0].value?.toFixed(3)}</p>
      <p className="text-slate-500 text-xs mt-0.5">{payload[0].payload?.time}</p>
    </div>
  );
}

export default function SensorChart({ config, data }) {
  const latest  = data[data.length - 1]?.value;
  const prev    = data[data.length - 2]?.value;
  const isSpike = data.length >= 2 && prev != null && Math.abs(latest - prev) > Math.abs(prev) * 0.25;
  const color   = isSpike ? "#ef4444" : "#06b6d4";
  const gradId  = `grad-${config.sensor?.replace(/[^a-z0-9]/gi, "-")}`;

  return (
    <motion.div
      className="h-full bg-slate-900 rounded-2xl border border-slate-800 flex flex-col p-4 overflow-hidden"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      {/* Header row */}
      <div className="flex items-start justify-between mb-3 shrink-0">
        <div>
          <h3 className="text-sm font-semibold text-white leading-tight">{config.title}</h3>
          <p className="text-xs text-slate-500 mt-0.5">{config.sensor}</p>
        </div>
        <div className="text-right">
          <motion.p
            key={latest}
            initial={{ opacity: 0.5, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className={`text-2xl font-black leading-none ${isSpike ? "text-red-400" : "text-cyan-400"}`}
          >
            {latest != null ? latest.toFixed(2) : "—"}
          </motion.p>
          {isSpike && (
            <span className="text-[10px] font-semibold text-red-400 animate-pulse mt-0.5 block">
              ⚡ SPIKE
            </span>
          )}
        </div>
      </div>

      {/* Chart */}
      <div className="flex-1 min-h-0">
        {data.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <p className="text-slate-600 text-xs">Awaiting data stream…</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 2, bottom: 0, left: -22 }}>
              <defs>
                <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor={color} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={color} stopOpacity={0}    />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis
                dataKey="time"
                tick={{ fill: "#475569", fontSize: 9 }}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis tick={{ fill: "#475569", fontSize: 9 }} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="value"
                stroke={color}
                strokeWidth={2}
                fill={`url(#${gradId})`}
                dot={false}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </motion.div>
  );
}
