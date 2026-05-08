"""
PulseGuard — Multithreaded Sensor Simulator
────────────────────────────────────────────
• Each sensor runs in its own thread, POSTing to /api/v1/telemetry.
• Normal behaviour: Sine wave + Gaussian noise.
• Anomaly injection: Every 60 s a critical spike is fired (110–130% of range).
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
