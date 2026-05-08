import SensorChart      from "./SensorChart";
import StatusCard       from "./StatusCard";
import AlertFeed        from "./AlertFeed";

/**
 * Registry maps backend "type" strings → React components.
 * Add new component types here — no other file needs changing.
 */
const REGISTRY = {
  chart:       SensorChart,
  status_card: StatusCard,
  alert_feed:  AlertFeed,
};

/**
 * Grid span classes per "size" value from UI-Schema.
 * Tailwind class names must be complete strings (no dynamic concatenation).
 */
const SIZE_COLS = {
  large:  "col-span-2",
  medium: "col-span-1",
  small:  "col-span-1",
};
const SIZE_ROWS = {
  large:  "row-span-2",
  medium: "row-span-2",
  small:  "row-span-1",
};

export default function ComponentRegistry({ schema, alerts, sensorData, onDismiss }) {
  if (!schema?.components?.length) return null;

  return (
    <div className="grid grid-cols-4 gap-4 auto-rows-[210px]">
      {schema.components.map((comp, idx) => {
        const Component = REGISTRY[comp.type];
        if (!Component) return null;

        return (
          <div
            key={idx}
            className={`${SIZE_COLS[comp.size] ?? SIZE_COLS.medium} ${SIZE_ROWS[comp.size] ?? SIZE_ROWS.medium}`}
          >
            <Component
              config={comp}
              data={sensorData[comp.sensor] || []}
              alerts={alerts}
              onDismiss={onDismiss}
            />
          </div>
        );
      })}
    </div>
  );
}
