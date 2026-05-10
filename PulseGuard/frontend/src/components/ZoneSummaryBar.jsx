/**
 * ZoneSummaryBar — sticky header bar showing live health for each zone.
 *
 * Displays Z1 / Z2 / Z3 pills whose colour reflects real-time zone health:
 *   ok       → emerald
 *   warning  → amber
 *   critical → red (pulsing)
 *
 * Health data is fetched from GET /api/v1/zones/health on mount and
 * refreshed every 5 s, or overridden by the `zoneHealth` prop when the
 * parent derives it from WebSocket sensor_ping messages (zero extra fetches).
 *
 * Props:
 *   zoneHealth  {Object}  Optional override: { Z1: "ok"|"warning"|"critical" }
 *   sensorPings {Object}  Optional raw pings map to compute health client-side
 */
import { useEffect, useState } from "react";
import { motion }              from "framer-motion";
import { api }                 from "../services/api";

const ZONE_LABELS = {
  Z1: "Z1 · Furnace",
  Z2: "Z2 · Hydraulics",
  Z3: "Z3 · Cooling",
};

const STATUS_STYLES = {
  critical: {
    bg:   "bg-red-950/60",
    ring: "ring-red-500/60",
    dot:  "bg-red-500 animate-ping",
    text: "text-red-400",
  },
  warning: {
    bg:   "bg-amber-950/50",
    ring: "ring-amber-400/50",
    dot:  "bg-amber-400",
    text: "text-amber-300",
  },
  ok: {
    bg:   "bg-emerald-950/40",
    ring: "ring-emerald-500/30",
    dot:  "bg-emerald-500",
    text: "text-emerald-400",
  },
  unknown: {
    bg:   "bg-slate-800/40",
    ring: "ring-slate-600/30",
    dot:  "bg-slate-500",
    text: "text-slate-400",
  },
};

/** Derive a coarse zone health from the raw sensorPings map. */
function deriveZoneHealth(sensorPings) {
  const zoneStatus = {};
  for (const [, ping] of Object.entries(sensorPings)) {
    const z = ping.zone;
    if (!z) continue;
    const prev = zoneStatus[z] ?? "ok";
    if (ping.status === "critical") {
      zoneStatus[z] = "critical";
    } else if (ping.status === "warning" && prev !== "critical") {
      zoneStatus[z] = "warning";
    } else if (!zoneStatus[z]) {
      zoneStatus[z] = "ok";
    }
  }
  return zoneStatus;
}

export default function ZoneSummaryBar({ zoneHealth: propHealth, sensorPings = {} }) {
  const [fetchedHealth, setFetchedHealth] = useState({});

  useEffect(() => {
    let mounted = true;
    const poll = async () => {
      try {
        const { data } = await api.get("/api/v1/zones/health");
        if (mounted) setFetchedHealth(data);
      } catch {
        // silently ignore — fallback to derived health
      }
    };
    poll();
    const interval = setInterval(poll, 5000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  // Merge sources: propHealth > derived from pings > fetched
  const derived  = deriveZoneHealth(sensorPings);
  const health   = { ...fetchedHealth, ...derived, ...(propHealth ?? {}) };
  const zones    = ["Z1", "Z2", "Z3"];

  return (
    <div className="flex items-center gap-2 px-2">
      {zones.map((zone) => {
        const status = health[zone] ?? "unknown";
        const styles = STATUS_STYLES[status];
        return (
          <motion.div
            key={zone}
            layout
            className={`
              flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold
              ring-1 ${styles.ring} ${styles.bg} ${styles.text}
              tracking-wide uppercase select-none
            `}
            animate={status === "critical" ? { opacity: [1, 0.7, 1] } : { opacity: 1 }}
            transition={status === "critical" ? { duration: 1.2, repeat: Infinity } : {}}
          >
            <span className={`relative flex h-2 w-2 rounded-full shrink-0 ${styles.dot}`} />
            {ZONE_LABELS[zone] ?? zone}
          </motion.div>
        );
      })}
    </div>
  );
}
