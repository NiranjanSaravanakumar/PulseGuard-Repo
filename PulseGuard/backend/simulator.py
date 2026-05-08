"""
PulseGuard — Complex Factory Floor Simulator  (3 Zones × 4 Sensor Types)
─────────────────────────────────────────────────────────────────────────
Zone 1 — Furnace Bay       (high temp, high pressure)
Zone 2 — Hydraulics Room   (pressure-critical, vibration-sensitive)
Zone 3 — Cooling Circuit   (flow-critical, moderate temp)

• Each sensor runs in its own daemon thread.
• Normal: sine-wave baseline + Gaussian noise.
• Anomaly (every 60 s): 1-3 sensors in a random zone spike simultaneously
  to trigger ZONE_ALARM in the AI engine.
• Velocity injection (every 120 s): one sensor ramps linearly toward threshold
  to trigger PREDICTION alerts.
"""
import math
import os
import random
import threading
import time

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL       = os.getenv("API_URL", "http://localhost:8000")
TELEMETRY_URL = f"{API_URL}/api/v1/telemetry"
INTERVAL      = float(os.getenv("SIMULATOR_INTERVAL", "2"))

# ── Sensor definitions ────────────────────────────────────────────────────────
# Each entry: id, unit, sector, zone, baseline, amplitude, frequency, threshold
SENSORS: list[dict] = [
    # Zone 1 — Furnace Bay
    {"id": "temp_sensor_z1",      "unit": "°C",    "sector": "Furnace",    "zone": "Z1", "base": 80.0,  "amp": 12.0, "freq": 0.04, "threshold": 120.0},
    {"id": "pressure_sensor_z1",  "unit": "bar",   "sector": "Furnace",    "zone": "Z1", "base": 110.0, "amp": 18.0, "freq": 0.03, "threshold": 160.0},
    {"id": "vibration_sensor_z1", "unit": "mm/s",  "sector": "Furnace",    "zone": "Z1", "base": 2.0,   "amp": 1.0,  "freq": 0.07, "threshold": 8.0},
    {"id": "flow_sensor_z1",      "unit": "L/min", "sector": "Furnace",    "zone": "Z1", "base": 35.0,  "amp": 6.0,  "freq": 0.05, "threshold": 10.0},
    # Zone 2 — Hydraulics Room
    {"id": "temp_sensor_z2",      "unit": "°C",    "sector": "Hydraulics", "zone": "Z2", "base": 65.0,  "amp": 8.0,  "freq": 0.06, "threshold": 100.0},
    {"id": "pressure_sensor_z2",  "unit": "bar",   "sector": "Hydraulics", "zone": "Z2", "base": 130.0, "amp": 25.0, "freq": 0.04, "threshold": 200.0},
    {"id": "vibration_sensor_z2", "unit": "mm/s",  "sector": "Hydraulics", "zone": "Z2", "base": 3.5,   "amp": 1.5,  "freq": 0.09, "threshold": 10.0},
    {"id": "flow_sensor_z2",      "unit": "L/min", "sector": "Hydraulics", "zone": "Z2", "base": 28.0,  "amp": 5.0,  "freq": 0.05, "threshold": 8.0},
    # Zone 3 — Cooling Circuit
    {"id": "temp_sensor_z3",      "unit": "°C",    "sector": "Cooling",    "zone": "Z3", "base": 45.0,  "amp": 6.0,  "freq": 0.05, "threshold": 75.0},
    {"id": "pressure_sensor_z3",  "unit": "bar",   "sector": "Cooling",    "zone": "Z3", "base": 85.0,  "amp": 12.0, "freq": 0.03, "threshold": 130.0},
    {"id": "vibration_sensor_z3", "unit": "mm/s",  "sector": "Cooling",    "zone": "Z3", "base": 1.5,   "amp": 0.8,  "freq": 0.08, "threshold": 6.0},
    {"id": "flow_sensor_z3",      "unit": "L/min", "sector": "Cooling",    "zone": "Z3", "base": 50.0,  "amp": 10.0, "freq": 0.04, "threshold": 15.0},
]

SENSOR_BY_ID  = {s["id"]: s for s in SENSORS}
ZONE_SENSORS  = {}
for s in SENSORS:
    ZONE_SENSORS.setdefault(s["zone"], []).append(s["id"])

_stop_flag        = threading.Event()

# Shared override dict: sensor_id → override_value (used by injection threads)
_lock             = threading.Lock()
_value_overrides: dict[str, float] = {}


# ── HTTP helper ───────────────────────────────────────────────────────────────
def _post(sensor: dict, value: float) -> None:
    payload = {
        "sensor_id": sensor["id"],
        "value":     round(value, 3),
        "unit":      sensor["unit"],
        "sector":    sensor["sector"],
        "zone":      sensor["zone"],
        "threshold": sensor["threshold"],
    }
    try:
        resp   = requests.post(TELEMETRY_URL, json=payload, timeout=5)
        result = resp.json()
        alerts = result.get("alerts", [])
        tag    = f"  [{sensor['id']}] {value:.2f} {sensor['unit']}"
        if alerts:
            print(f"{tag}  !!ALERT!! {alerts}")
        else:
            print(tag)
    except requests.RequestException as exc:
        print(f"  [ERR] {sensor['id']}: {exc}")


# ── Per-sensor normal thread ──────────────────────────────────────────────────
def _sensor_thread(sensor: dict) -> None:
    t = random.uniform(0, 2 * math.pi)
    while not _stop_flag.is_set():
        with _lock:
            override = _value_overrides.pop(sensor["id"], None)

        if override is not None:
            value = override
        else:
            sine  = sensor["base"] + sensor["amp"] * math.sin(2 * math.pi * sensor["freq"] * t)
            value = sine + random.gauss(0, sensor["amp"] * 0.05)

        _post(sensor, value)
        t += INTERVAL
        time.sleep(INTERVAL)


# ── Zone anomaly injector (every 60 s) ───────────────────────────────────────
def _zone_anomaly_injector() -> None:
    """Every 60 s, spike 3 sensors in a random zone simultaneously."""
    while not _stop_flag.is_set():
        time.sleep(60)
        if _stop_flag.is_set():
            break

        zone = random.choice(list(ZONE_SENSORS.keys()))
        targets = random.sample(ZONE_SENSORS[zone], min(3, len(ZONE_SENSORS[zone])))
        print(f"\n[ZONE INJECTION] Zone {zone} — spiking {targets}")

        with _lock:
            for sid in targets:
                s   = SENSOR_BY_ID[sid]
                val = s["threshold"] * random.uniform(1.12, 1.30)
                _value_overrides[sid] = val

        print("[ZONE INJECTION] done — AI engine should generate ZONE_ALARM\n")


# ── Velocity ramp injector (every 120 s) ─────────────────────────────────────
def _velocity_ramp_injector() -> None:
    """
    Every 120 s, pick one sensor and ramp it linearly toward threshold
    over ~25 readings so the AI prediction fires before breach.
    """
    while not _stop_flag.is_set():
        time.sleep(120)
        if _stop_flag.is_set():
            break

        sensor = random.choice(SENSORS)
        start  = sensor["base"]
        end    = sensor["threshold"] * 0.98   # ramp to just below threshold
        steps  = 20
        print(f"\n[VELOCITY RAMP] Ramping {sensor['id']}: {start:.1f} → {end:.1f} over {steps} ticks")

        for i in range(steps):
            if _stop_flag.is_set():
                break
            val = start + (end - start) * (i / steps)
            with _lock:
                _value_overrides[sensor["id"]] = val
            time.sleep(INTERVAL * 1.1)   # slightly faster than normal tick

        print(f"[VELOCITY RAMP] {sensor['id']} ramp complete\n")


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 60)
    print("  PulseGuard Factory Floor Simulator  v3")
    print(f"  Target : {TELEMETRY_URL}")
    print(f"  Sensors: {len(SENSORS)} across {len(ZONE_SENSORS)} zones")
    print(f"  Tick   : {INTERVAL}s | Zone alarm: 60s | Velocity: 120s")
    print("=" * 60)

    threads = [threading.Thread(target=_sensor_thread,        args=(s,), daemon=True) for s in SENSORS]
    threads.append(threading.Thread(target=_zone_anomaly_injector, daemon=True))
    threads.append(threading.Thread(target=_velocity_ramp_injector, daemon=True))

    for t in threads:
        t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nSimulator shutdown.")
        _stop_flag.set()


if __name__ == "__main__":
    main()
import math
import os
import random
import threading
import time

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL       = os.getenv("API_URL", "http://localhost:8000")
TELEMETRY_URL = f"{API_URL}/api/v1/telemetry"
INTERVAL      = float(os.getenv("SIMULATOR_INTERVAL", "2"))

SENSORS: list[dict] = [
    {"id": "temp_sensor_01",      "unit": "°C",    "sector": "Furnace",    "base": 75.0,  "amplitude": 15.0, "freq": 0.05},
    {"id": "pressure_sensor_01",  "unit": "bar",   "sector": "Hydraulics", "base": 100.0, "amplitude": 20.0, "freq": 0.03},
    {"id": "vibration_sensor_01", "unit": "mm/s",  "sector": "Pumps",      "base": 2.5,   "amplitude": 1.5,  "freq": 0.07},
    {"id": "flow_sensor_01",      "unit": "L/min", "sector": "Cooling",    "base": 30.0,  "amplitude": 8.0,  "freq": 0.04},
]

_anomaly_flag = threading.Event()
_stop_flag    = threading.Event()


def _anomaly_scheduler() -> None:
    """Toggle anomaly flag for 2 s every 60 s."""
    while not _stop_flag.is_set():
        time.sleep(60)
        if _stop_flag.is_set():
            break
        print("\n[!] ANOMALY INJECTION WINDOW OPEN")
        _anomaly_flag.set()
        time.sleep(2)
        _anomaly_flag.clear()
        print("[!] anomaly window closed\n")


def _post(payload: dict) -> None:
    try:
        resp   = requests.post(TELEMETRY_URL, json=payload, timeout=5)
        status = "ALERT  <--" if resp.json().get("alert_generated") else "ok"
        print(f"  [{payload['sensor_id']}] {payload['value']:.3f} {payload['unit']}  -> {status}")
    except requests.RequestException as exc:
        print(f"  [ERROR] {payload['sensor_id']}: {exc}")


def _sensor_thread(sensor: dict) -> None:
    t = random.uniform(0, 2 * math.pi)  # random phase offset
    while not _stop_flag.is_set():
        sine_val = sensor["base"] + sensor["amplitude"] * math.sin(
            2 * math.pi * sensor["freq"] * t
        )
        noise = random.gauss(0, sensor["amplitude"] * 0.05)

        if _anomaly_flag.is_set():
            # Spike to 110–130% of (base + amplitude)
            peak  = sensor["base"] + sensor["amplitude"]
            value = peak * random.uniform(1.10, 1.30)
        else:
            value = sine_val + noise

        _post({
            "sensor_id": sensor["id"],
            "value":     round(value, 3),
            "unit":      sensor["unit"],
            "sector":    sensor["sector"],
        })

        t += INTERVAL
        time.sleep(INTERVAL)


def main() -> None:
    print(f"PulseGuard Simulator  |  target: {TELEMETRY_URL}")
    print(f"Sensors: {len(SENSORS)}  |  interval: {INTERVAL}s  |  anomaly every 60s\n")

    threads = [
        threading.Thread(target=_sensor_thread, args=(s,), daemon=True)
        for s in SENSORS
    ]
    threads.append(threading.Thread(target=_anomaly_scheduler, daemon=True))

    for t in threads:
        t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nSimulator stopped.")
        _stop_flag.set()


if __name__ == "__main__":
    main()
