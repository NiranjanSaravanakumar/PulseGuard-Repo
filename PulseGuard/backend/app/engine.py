"""
PulseGuard AI Engine
────────────────────
• Sliding Window Anomaly Detection:
  If current value > 2 σ from last 10 readings → CRITICAL alert.
• Criticality Score = (deviation*10)*0.4 + priority*0.3 + rate_of_change*0.3
  clamped to [0, 100].
"""
from datetime import datetime, timezone

import numpy as np

from .database import get_db
from .models import Alert, Severity, SensorReading, TelemetryPayload

WINDOW_SIZE: int = 10
STD_THRESHOLD: float = 2.0

# Higher number = higher priority in scoring
SENSOR_PRIORITY: dict[str, float] = {
    "temp_sensor_01":      10.0,
    "pressure_sensor_01":   8.0,
    "vibration_sensor_01":  7.0,
    "flow_sensor_01":       6.0,
}


async def _get_recent_values(sensor_id: str, n: int = WINDOW_SIZE) -> list[float]:
    """Return last *n* stored values for the sensor (newest first)."""
    db = get_db()
    cursor = (
        db["sensor_readings"]
        .find({"sensor_id": sensor_id}, {"value": 1, "_id": 0})
        .sort("timestamp", -1)
        .limit(n)
    )
    docs = await cursor.to_list(length=n)
    return [d["value"] for d in docs]


def _criticality_score(
    deviation: float, priority: float, rate_of_change: float
) -> float:
    raw = (deviation * 10 * 0.4) + (priority * 0.3) + (min(rate_of_change, 30.0) * 0.3)
    return round(min(max(raw, 0.0), 100.0), 2)


async def process_reading(
    payload: TelemetryPayload,
) -> tuple[SensorReading, Alert | None]:
    """
    Persist the reading, then run sliding-window anomaly detection.
    Returns (reading, alert_or_None).
    """
    db = get_db()

    reading = SensorReading(
        sensor_id=payload.sensor_id,
        value=payload.value,
        unit=payload.unit,
        sector=payload.sector,
        metadata=payload.metadata,
        timestamp=datetime.now(timezone.utc),
    )

    # ── Persist raw reading ───────────────────────────────────────────────────
    await db["sensor_readings"].insert_one(reading.model_dump())

    # ── Sliding Window Anomaly Detection ─────────────────────────────────────
    recent = await _get_recent_values(payload.sensor_id)
    if len(recent) < 3:
        return reading, None  # insufficient history

    arr = np.array(recent, dtype=float)
    mean = float(np.mean(arr))
    std = float(np.std(arr))

    if std == 0.0:
        return reading, None

    deviation = abs(payload.value - mean) / std
    rate_of_change = abs(payload.value - recent[0])
    priority = SENSOR_PRIORITY.get(payload.sensor_id, 5.0)
    score = _criticality_score(deviation, priority, rate_of_change)

    if deviation > STD_THRESHOLD:
        alert = Alert(
            sensor_id=payload.sensor_id,
            severity=Severity.CRITICAL,
            message=(
                f"[{payload.sensor_id}] Anomaly — value {payload.value:.2f} "
                f"is {deviation:.1f}σ from μ={mean:.2f} (σ={std:.2f})"
            ),
            criticality_score=score,
            value=payload.value,
            mean=mean,
            std_dev=std,
        )
        await db["alerts"].insert_one(alert.model_dump())
        return reading, alert

    return reading, None
