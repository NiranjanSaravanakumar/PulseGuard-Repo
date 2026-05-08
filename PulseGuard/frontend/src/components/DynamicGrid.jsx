/**
 * DynamicGrid — metadata-driven layout engine.
 */
import { Suspense } from "react";
import AlertFeed       from "./AlertFeed";
import SensorChart     from "./SensorChart";
import StatusCard      from "./StatusCard";
import DigitalTwinGrid from "./DigitalTwinGrid";

// ── Inline Radial Gauge (SVG-based, no extra deps) ────────────────────────────
function RadialGauge({ label = "", value = 0, max = 150, unit = "" }) {
  const pct   = Math.min(Math.max(value / max, 0), 1);
  const color = pct > 0.85 ? "#f85149" : pct > 0.65 ? "#d29922" : "#3fb950";
  // Arc: 270° sweep, from 135° to 405° (i.e. -135° to +135°)
  const DASH_TOTAL = 141;
  return (
    <div className="flex flex-col items-center justify-center bg-slate-800/60 rounded-2xl p-4 h-full">
      <svg viewBox="0 0 100 80" className="w-28 h-20">
        {/* Track */}
        <path
          d="M10,70 A45,45 0 1,1 90,70"
          fill="none" stroke="#334155" strokeWidth="8" strokeLinecap="round"
        />
        {/* Fill */}
        <path
          d="M10,70 A45,45 0 1,1 90,70"
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={`${pct * DASH_TOTAL} ${DASH_TOTAL}`}
        />
        <text x="50" y="66" textAnchor="middle" fill="white" fontSize="15" fontWeight="bold">
          {typeof value === "number" ? value.toFixed(1) : "—"}
        </text>
        {unit && (
          <text x="50" y="76" textAnchor="middle" fill="#8b949e" fontSize="7">
            {unit}
          </text>
        )}
      </svg>
      <span className="text-xs text-slate-400 mt-1 truncate max-w-full text-center">{label}</span>
    </div>
  );
}

// ── Component mapper ──────────────────────────────────────────────────────────
function ComponentMapper({ comp, sensorData, sensorPings, alerts, onDismiss }) {
  const source   = comp.source || comp.sensor;
  const readings = sensorData[source] || [];
  const latest   = readings.at(-1)?.value ?? null;

  switch (comp.type) {
    case "digital_twin":
      return <DigitalTwinGrid pings={sensorPings} />;

    case "alert_feed":
      return <AlertFeed alerts={alerts} onDismiss={onDismiss} label={comp.label} />;

    case "status_card":
      return (
        <StatusCard
          sensorId={source}
          label={comp.label || source}
          value={latest}
          readings={readings}
        />
      );

    case "radial_gauge":
      return <RadialGauge label={comp.label || source} value={latest ?? 0} />;

    case "line_chart":
    case "area_chart":
    case "bar_chart": {
      const typeMap = { line_chart: "line", area_chart: "area", bar_chart: "bar" };
      return (
        <SensorChart
          sensorId={source}
          label={comp.label || source}
          data={readings}
          chartType={typeMap[comp.type] || "line"}
        />
      );
    }

    default:
      return (
        <div className="flex items-center justify-center h-full text-slate-500 text-sm italic">
          Unknown: <code className="ml-1 text-slate-400">{comp.type}</code>
        </div>
      );
  }
}

// ── Size → Tailwind column-span map ──────────────────────────────────────────
const SIZE_CLASS = {
  small:  "col-span-1",
  medium: "col-span-1 lg:col-span-2",
  large:  "col-span-1 lg:col-span-2 xl:col-span-2",
};

// ── DynamicGrid ───────────────────────────────────────────────────────────────
export default function DynamicGrid({ schema, sensorData, sensorPings = {}, alerts, onDismiss }) {
  // Loading state
  if (!schema) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center space-y-3">
          <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-slate-400 text-sm">Loading layout schema…</p>
        </div>
      </div>
    );
  }

  const { components = [] } = schema;

  // Empty — no data yet
  if (components.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400 text-lg tracking-wide">
        Waiting for Data…
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 p-4">
      {components.map((comp, idx) => {
        const key = `${comp.type}-${comp.source || comp.sensor || idx}`;
        return (
          <div
            key={key}
            className={`${SIZE_CLASS[comp.size] ?? "col-span-1"} min-h-[200px]`}
          >
            <Suspense
              fallback={
                <div className="animate-pulse bg-slate-800/60 rounded-2xl h-full" />
              }
            >
              <ComponentMapper
                comp={comp}
                sensorData={sensorData}
                sensorPings={sensorPings}
                alerts={alerts}
                onDismiss={onDismiss}
              />
            </Suspense>
          </div>
        );
      })}
    </div>
  );
}
