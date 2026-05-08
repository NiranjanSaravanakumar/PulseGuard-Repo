"""
PulseGuard — PredictiveHMI AI Engine v3
────────────────────────────────────────
• Sliding Window Anomaly Detection  (N=10, 2σ → CRITICAL)
• Velocity-of-Failure / Trend Analysis  (N=20, 30 s window → PREDICTION)
• Event Collapsing / Smart Aggregation  (zone threshold: ≥3 sensors → ZONE_ALARM)
• Criticality Score  (0–100)
"""
from collections import defaultdict
from datetime import datetime, timezone
from typing import NamedTuple

import numpy as np

from .database import get_db
from .models import Alert, Severity, SensorReading, TelemetryPayload

# ── Tuneable constants ────────────────────────────────────────────────────────
WINDOW_ANOMALY: int    = 10      # readings for σ-based anomaly
WINDOW_VELOCITY: int   = 20      # readings for linear trend
STD_THRESHOLD: float   = 2.0     # σ multiplier for CRITICAL
PREDICTION_ETA: float  = 30.0    # seconds: if breach predicted within this → PREDICTION
ZONE_SENSOR_MIN: int   = 3       # how many sensors must fire to collapse into ZONE_ALARM
ZONE_WINDOW_SEC: float = 10.0    # collapse window in seconds

# In-memory zone-collapse buffer  {zone → [(sensor_id, timestamp)]}
_zone_buffer: dict[str, list[tuple[str, float]]] = defaultdict(list)

# Sensor metadata: (priority 0-10, normal_max for velocity calculation)
SENSOR_META: dict[str, tuple[float, float]] = {
    "temp_sensor_z1":      (10.0, 100.0),
    "temp_sensor_z2":      (10.0, 100.0),
    "temp_sensor_z3":      (10.0, 100.0),
    "pressure_sensor_z1":  (8.0,  150.0),
    "pressure_sensor_z2":  (8.0,  150.0),
    "pressure_sensor_z3":  (8.0,  150.0),
    "vibration_sensor_z1": (7.0,   10.0),
    "vibration_sensor_z2": (7.0,   10.0),
    "vibration_sensor_z3": (7.0,   10.0),
    "flow_sensor_z1":      (6.0,   60.0),
    "flow_sensor_z2":      (6.0,   60.0),
    "flow_sensor_z3":      (6.0,   60.0),
}


class EngineResult(NamedTuple):
    reading: SensorReading
    alert: Alert | None
    prediction: Alert | None
    zone_alarm: Alert | None


# ── Helpers ───────────────────────────────────────────────────────────────────
async def _get_recent(sensor_id: str, n: int) -> list[tuple[float, datetime]]:
    """Return last *n* (value, timestamp) pairs newest-first."""
    db = get_db()
    cursor = (
        db["sensor_readings"]
        .find({"sensor_id": sensor_id}, {"value": 1, "timestamp": 1, "_id": 0})
        .sort("timestamp", -1)
        .limit(n)
    )
    docs = await cursor.to_list(length=n)
    return [(d["value"], d["timestamp"]) for d in docs]


def _criticality_score(deviation: float, priority: float, roc: float) -> float:
    raw = (deviation * 10 * 0.4) + (priority * 0.3) + (min(roc, 30.0) * 0.3)
    return round(min(max(raw, 0.0), 100.0), 2)


# ── Core processing ───────────────────────────────────────────────────────────
async def process_reading(payload: TelemetryPayload) -> EngineResult:
    """
    Persist → Anomaly detect → Velocity/trend predict → Zone collapse.
    Returns EngineResult(reading, alert, prediction, zone_alarm).
    """
    db  = get_db()
    now = datetime.now(timezone.utc)

    reading = SensorReading(
        sensor_id=payload.sensor_id,
        value=payload.value,
        unit=payload.unit,
        sector=payload.sector,
        zone=payload.zone,
        metadata=payload.metadata,
        timestamp=now,
    )
    await db["sensor_readings"].insert_one(reading.model_dump())

    priority, normal_max = SENSOR_META.get(payload.sensor_id, (5.0, 200.0))
    threshold = payload.threshold or normal_max * 1.15

    # ── 1. Anomaly Detection (σ-based) ────────────────────────────────────────
    anomaly_alert: Alert | None = None
    recent_n = await _get_recent(payload.sensor_id, WINDOW_ANOMALY)
    if len(recent_n) >= 3:
        values = [v for v, _ in recent_n]
        arr    = np.array(values, dtype=float)
        mean   = float(np.mean(arr))
        std    = float(np.std(arr))
        if std > 0:
            deviation = abs(payload.value - mean) / std
            roc       = abs(payload.value - values[0])
            score     = _criticality_score(deviation, priority, roc)
            if deviation > STD_THRESHOLD:
                anomaly_alert = Alert(
                    sensor_id=payload.sensor_id,
                    severity=Severity.CRITICAL,
                    message=(
                        f"[{payload.sensor_id}] Anomaly detected — "
                        f"value {payload.value:.2f} is {deviation:.1f}σ "
                        f"from μ={mean:.2f} (σ={std:.2f})"
                    ),
                    criticality_score=score,
                    value=payload.value,
                    mean=mean,
                    std_dev=std,
                    zone=payload.zone,
                    sector=payload.sector,
                )
                await db["alerts"].insert_one(anomaly_alert.model_dump())

    # ── 2. Velocity-of-Failure / Trend Prediction ─────────────────────────────
    prediction_alert: Alert | None = None
    if not anomaly_alert:   # skip if already CRITICAL — would be redundant
        recent_v = await _get_recent(payload.sensor_id, WINDOW_VELOCITY)
        if len(recent_v) >= 5:
            vals = np.array([v for v, _ in recent_v[::-1]], dtype=float)  # oldest→newest
            t_idx = np.arange(len(vals), dtype=float)
            # Linear regression via least squares
            coeffs = np.polyfit(t_idx, vals, 1)
            velocity_per_tick = float(coeffs[0])  # units / reading-tick

            # Estimate readings per second (using real timestamps)
            ts_list = [ts for _, ts in recent_v[::-1]]
            if len(ts_list) >= 2:
                total_sec = (ts_list[-1] - ts_list[0]).total_seconds()
                if total_sec > 0:
                    ticks_per_sec = (len(ts_list) - 1) / total_sec
                    velocity_per_sec = velocity_per_tick * ticks_per_sec

                    if velocity_per_sec > 0 and payload.value < threshold:
                        eta = (threshold - payload.value) / velocity_per_sec
                        if 0 < eta <= PREDICTION_ETA:
                            pred_score = min(100.0, (1 - eta / PREDICTION_ETA) * 100)
                            prediction_alert = Alert(
                                sensor_id=payload.sensor_id,
                                severity=Severity.PREDICTION,
                                message=(
                                    f"[PREDICTION] {payload.sensor_id} trending toward "
                                    f"threshold ({threshold:.1f}) — estimated breach "
                                    f"in {eta:.0f}s at +{velocity_per_sec:.3f}/s"
                                ),
                                criticality_score=round(pred_score, 2),
                                value=payload.value,
                                zone=payload.zone,
                                sector=payload.sector,
                                is_prediction=True,
                                eta_seconds=round(eta, 1),
                                velocity=round(velocity_per_sec, 4),
                            )
                            await db["alerts"].insert_one(prediction_alert.model_dump())

    # ── 3. Zone Event Collapsing ──────────────────────────────────────────────
    zone_alarm: Alert | None = None
    if (anomaly_alert or prediction_alert) and payload.zone:
        zone = payload.zone
        now_ts = now.timestamp()

        # Purge stale entries
        _zone_buffer[zone] = [
            (sid, t) for sid, t in _zone_buffer[zone]
            if now_ts - t <= ZONE_WINDOW_SEC
        ]
        # Add current sensor if not already present in window
        existing_ids = {sid for sid, _ in _zone_buffer[zone]}
        if payload.sensor_id not in existing_ids:
            _zone_buffer[zone].append((payload.sensor_id, now_ts))

        if len(_zone_buffer[zone]) >= ZONE_SENSOR_MIN:
            affected = [sid for sid, _ in _zone_buffer[zone]]
            zone_alarm = Alert(
                sensor_id=payload.sensor_id,
                severity=Severity.ZONE_ALARM,
                message=(
                    f"[ZONE ALARM] Zone {zone} — {len(affected)} sensors "
                    f"in distress: {', '.join(affected)}"
                ),
                criticality_score=95.0,
                value=payload.value,
                zone=zone,
                sector=payload.sector,
                is_zone_alarm=True,
                affected_sensors=affected,
                zone_summary=(
                    f"Zone {zone} multi-sensor event. "
                    f"{len(affected)} sensors exceeded safe operating range "
                    f"within {ZONE_WINDOW_SEC:.0f} s."
                ),
            )
            await db["alerts"].insert_one(zone_alarm.model_dump())
            _zone_buffer[zone].clear()   # reset after firing

    return EngineResult(reading, anomaly_alert, prediction_alert, zone_alarm)


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
