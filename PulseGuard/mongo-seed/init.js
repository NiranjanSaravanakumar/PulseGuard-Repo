// MongoDB seed — runs once on first container start
// Collections: ui_schemas, sensors, alerts

db = db.getSiblingDB("pulseguard");

// ── Sensor metadata ──────────────────────────────────────────────────────────
db.sensors.drop();
db.sensors.insertMany([
  {
    sensor_id: "temp-01",
    name: "Furnace Temperature",
    unit: "°C",
    priority: 10,
    sector: "Furnace",
    normal_range: { min: 60, max: 95 },
    critical_threshold: 105
  },
  {
    sensor_id: "pressure-01",
    name: "Hydraulic Pressure",
    unit: "bar",
    priority: 8,
    sector: "Hydraulics",
    normal_range: { min: 80, max: 120 },
    critical_threshold: 140
  },
  {
    sensor_id: "vibration-01",
    name: "Pump Vibration",
    unit: "mm/s",
    priority: 7,
    sector: "Pumps",
    normal_range: { min: 0, max: 4.5 },
    critical_threshold: 7
  },
  {
    sensor_id: "flow-01",
    name: "Coolant Flow",
    unit: "L/min",
    priority: 6,
    sector: "Cooling",
    normal_range: { min: 20, max: 40 },
    critical_threshold: 10
  }
]);

// ── UI Schemas ───────────────────────────────────────────────────────────────
db.ui_schemas.drop();

// Operator view — simplified, action-focused
db.ui_schemas.insertOne({
  role: "operator",
  layout: "grid",
  theme: "dark",
  components: [
    { type: "alert_feed",   label: "Active Alerts",         size: "large",  position: { col: 1, row: 1, span: 2 } },
    { type: "status_card",  sensor: "temp-01",              size: "medium", position: { col: 3, row: 1 } },
    { type: "status_card",  sensor: "pressure-01",          size: "medium", position: { col: 4, row: 1 } },
    { type: "chart",        sensor: "temp-01",    chartType: "line", size: "large",  position: { col: 1, row: 2, span: 2 } },
    { type: "chart",        sensor: "pressure-01",chartType: "area", size: "large",  position: { col: 3, row: 2, span: 2 } }
  ]
});

// Engineer view — full telemetry + AI details
db.ui_schemas.insertOne({
  role: "engineer",
  layout: "grid",
  theme: "dark",
  components: [
    { type: "alert_feed",   label: "Intelligence Feed",     size: "large",  position: { col: 1, row: 1, span: 2 } },
    { type: "status_card",  sensor: "temp-01",              size: "small",  position: { col: 3, row: 1 } },
    { type: "status_card",  sensor: "pressure-01",          size: "small",  position: { col: 4, row: 1 } },
    { type: "status_card",  sensor: "vibration-01",         size: "small",  position: { col: 3, row: 2 } },
    { type: "status_card",  sensor: "flow-01",              size: "small",  position: { col: 4, row: 2 } },
    { type: "chart",        sensor: "temp-01",    chartType: "line",        size: "medium", position: { col: 1, row: 3 } },
    { type: "chart",        sensor: "pressure-01",chartType: "area",        size: "medium", position: { col: 2, row: 3 } },
    { type: "chart",        sensor: "vibration-01",chartType: "bar",        size: "medium", position: { col: 3, row: 3 } },
    { type: "chart",        sensor: "flow-01",    chartType: "line",        size: "medium", position: { col: 4, row: 3 } }
  ]
});

print("PulseGuard seed complete — sensors and UI schemas loaded.");
