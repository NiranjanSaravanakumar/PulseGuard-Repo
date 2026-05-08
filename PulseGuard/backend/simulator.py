"""
PulseGuard — Data Simulator
• Sine-wave base values per sensor
• Gaussian noise overlay
• Critical Failure injection every 60 s (random spike to 110–250 %)
"""
import asyncio
import json
import math
import random
import time

import websockets

WS_URL = "ws://localhost:8000/ws/engineer"

SENSORS = [
    {"id": "temp-01",      "sector": "Zone-A", "base": 65.0,  "amp": 10.0,   "freq": 0.08},
    {"id": "temp-02",      "sector": "Zone-B", "base": 72.0,  "amp":  8.0,   "freq": 0.06},
    {"id": "pressure-01",  "sector": "Zone-A", "base":  4.5,  "amp":  0.5,   "freq": 0.05},
    {"id": "vibration-01", "sector": "Zone-C", "base":  0.02, "amp":  0.005, "freq": 0.12},
    {"id": "flow-01",      "sector": "Zone-B", "base": 120.0, "amp": 15.0,   "freq": 0.07},
]

TICK_INTERVAL   = 0.5   # seconds between batches (2 Hz)
CRITICAL_PERIOD = 60.0  # seconds between critical injection windows


async def run(ws_url: str) -> None:
    print(f"[PulseGuard Simulator] Connecting to {ws_url} …")

    async with websockets.connect(ws_url, ping_interval=20) as ws:
        print("[PulseGuard Simulator] ✓ Connected — streaming data")

        tick                  = 0
        last_critical_window  = time.time()

        while True:
            now            = time.time()
            trigger_spike  = (now - last_critical_window) >= CRITICAL_PERIOD
            spiked_this_cycle = False

            for sensor in SENSORS:
                # ── Sine wave + Gaussian noise ────────────────────────────
                value  = sensor["base"] + sensor["amp"] * math.sin(tick * sensor["freq"])
                value += random.gauss(0, sensor["amp"] * 0.04)

                # ── Critical Failure injection (once per window) ───────────
                if trigger_spike and not spiked_this_cycle and random.random() < 0.25:
                    multiplier = random.uniform(1.6, 2.5)
                    value     *= multiplier
                    spiked_this_cycle = True
                    print(
                        f"[!] CRITICAL SPIKE  sensor={sensor['id']}  "
                        f"value={value:.3f}  multiplier=×{multiplier:.2f}"
                    )

                payload = {
                    "type": "sensor_data",
                    "data": {
                        "sensor_id": sensor["id"],
                        "sector":    sensor["sector"],
                        "value":     round(value, 4),
                        "timestamp": now,
                    },
                }
                await ws.send(json.dumps(payload))

            if trigger_spike and spiked_this_cycle:
                last_critical_window = now

            tick += 1
            await asyncio.sleep(TICK_INTERVAL)


async def main() -> None:
    while True:
        try:
            await run(WS_URL)
        except (OSError, websockets.exceptions.WebSocketException) as exc:
            print(f"[PulseGuard Simulator] Connection lost ({exc}). Retrying in 3 s …")
            await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())
