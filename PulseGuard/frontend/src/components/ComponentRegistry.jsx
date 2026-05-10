/**
 * ComponentRegistry -- v4
 * ==========================================================================
 * Central registry mapping component type strings to their React
 * implementations, display metadata, and default layout config.
 *
 * Consumed by:
 *  - DynamicGrid.jsx     (resolveComponent for rendering)
 *  - CommandPalette.jsx  (registryEntries for palette browser)
 *
 * To add a new widget: build component, import here, add REGISTRY entry.
 */

import AlertFeed       from "./AlertFeed";
import DigitalTwinGrid from "./DigitalTwinGrid";
import RadialGauge     from "./RadialGauge";
import SensorChart     from "./SensorChart";
import StatusCard      from "./StatusCard";

// ---------------------------------------------------------------------------
export const REGISTRY = {
  digital_twin: {
    label:           "Digital Twin",
    icon:            "??",
    description:     "3-zone factory floor with pulsing live sensor nodes",
    component:       DigitalTwinGrid,
    defaultSize:     "large",
    defaultPosition: { x: 0, y: 0, w: 4, h: 3 },
    needsSource:     false,
  },

  alert_feed: {
    label:           "Intelligence Feed",
    icon:            "?",
    description:     "CRITICAL, PREDICTION, and ZONE_ALARM events with AI context",
    component:       AlertFeed,
    defaultSize:     "large",
    defaultPosition: { x: 0, y: 3, w: 2, h: 4 },
    needsSource:     false,
  },

  status_card: {
    label:           "Status Card",
    icon:            "??",
    description:     "Live sensor value with Neon colour-coded trend bar",
    component:       StatusCard,
    defaultSize:     "small",
    defaultPosition: { x: 0, y: 0, w: 1, h: 2 },
    needsSource:     true,
  },

  radial_gauge: {
    label:           "Radial Gauge",
    icon:            "??",
    description:     "SVG arc gauge -- value as % of normal max",
    component:       RadialGauge,
    defaultSize:     "small",
    defaultPosition: { x: 0, y: 0, w: 1, h: 2 },
    needsSource:     true,
  },

  line_chart: {
    label:           "Line Chart",
    icon:            "??",
    description:     "60-point rolling time-series line chart",
    component:       SensorChart,
    defaultSize:     "medium",
    defaultPosition: { x: 0, y: 0, w: 2, h: 2 },
    needsSource:     true,
    chartType:       "line",
  },

  area_chart: {
    label:           "Area Chart",
    icon:            "??",
    description:     "Filled area chart with gradient fill",
    component:       SensorChart,
    defaultSize:     "medium",
    defaultPosition: { x: 0, y: 0, w: 2, h: 2 },
    needsSource:     true,
    chartType:       "area",
  },

  bar_chart: {
    label:           "Bar Chart",
    icon:            "??",
    description:     "Periodic bar chart for discrete sensor readings",
    component:       SensorChart,
    defaultSize:     "medium",
    defaultPosition: { x: 0, y: 0, w: 2, h: 2 },
    needsSource:     true,
    chartType:       "bar",
  },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Look up a component type and render it with the provided context props.
 * Returns null for unknown types.
 */
export function resolveComponent(comp, contextProps = {}) {
  const entry = REGISTRY[comp.type];
  if (!entry) return null;

  const Comp      = entry.component;
  const chartType = entry.chartType ?? comp.chart_type;
  const source    = comp.source ?? comp.sensor;

  return (
    <Comp
      {...contextProps}
      sensorId={source}
      source={source}
      label={comp.label ?? entry.label}
      chartType={chartType}
    />
  );
}

/**
 * Return every entry as a flat array -- used by the component browser
 * in CommandPalette and any future drag-to-add palette.
 */
export function registryEntries() {
  return Object.entries(REGISTRY).map(([type, meta]) => ({ type, ...meta }));
}

/** Display label for a type, with fallback to raw type string. */
export function labelForType(type) {
  return REGISTRY[type]?.label ?? type;
}
