/**
 * RadialGauge — standalone SVG arc gauge component.
 *
 * Renders a 270° sweep arc showing `value` as a percentage of `max`.
 * Colour progresses green → amber → red based on the percentage.
 * Extracted from DynamicGrid so the ComponentRegistry can reference it
 * as a standalone type ("radial_gauge").
 *
 * Props:
 *   label   {string}  — displayed below the arc
 *   value   {number}  — current reading
 *   max     {number}  — upper bound (defaults to 150)
 *   unit    {string}  — optional unit label inside the arc
 */
import { motion } from "framer-motion";

export default function RadialGauge({ label = "", value = 0, max = 150, unit = "" }) {
  const pct   = Math.min(Math.max((value ?? 0) / max, 0), 1);
  const color = pct > 0.85 ? "#f85149" : pct > 0.65 ? "#d29922" : "#3fb950";

  // Arc: 270° sweep drawn with a strokeDasharray trick.
  // Total arc perimeter for a 45-radius path ≈ 141 px
  const DASH_TOTAL = 141;
  const filled     = pct * DASH_TOTAL;

  return (
    <div className="flex flex-col items-center justify-center h-full bg-slate-800/60 backdrop-blur-md rounded-2xl p-4 border border-slate-700/40">
      <svg viewBox="0 0 100 80" className="w-28 h-20 overflow-visible">
        {/* Track */}
        <path
          d="M10,70 A45,45 0 1,1 90,70"
          fill="none"
          stroke="#1e293b"
          strokeWidth="8"
          strokeLinecap="round"
        />
        {/* Glow layer */}
        <path
          d="M10,70 A45,45 0 1,1 90,70"
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={`${filled} ${DASH_TOTAL}`}
          opacity={0.15}
        />
        {/* Fill */}
        <motion.path
          d="M10,70 A45,45 0 1,1 90,70"
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={`${filled} ${DASH_TOTAL}`}
          initial={{ strokeDasharray: `0 ${DASH_TOTAL}` }}
          animate={{ strokeDasharray: `${filled} ${DASH_TOTAL}` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
        {/* Value text */}
        <text
          x="50"
          y="63"
          textAnchor="middle"
          fill="white"
          fontSize="15"
          fontWeight="bold"
          fontFamily="monospace"
        >
          {typeof value === "number" ? value.toFixed(1) : "—"}
        </text>
        {unit && (
          <text x="50" y="74" textAnchor="middle" fill="#64748b" fontSize="7">
            {unit}
          </text>
        )}
      </svg>

      {/* Percentage bar */}
      <div className="w-full mt-2 h-[2px] bg-slate-700/60 rounded-full overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ background: color }}
          initial={{ width: "0%" }}
          animate={{ width: `${pct * 100}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        />
      </div>

      <span className="text-[11px] text-slate-400 mt-2 truncate max-w-full text-center tracking-wide">
        {label}
      </span>
    </div>
  );
}
