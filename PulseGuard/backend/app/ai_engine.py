"""
PulseGuard — PredictiveHMI AI Engine  v4
═══════════════════════════════════════════════════════════════════════════════
Class-based singleton engine with three independent detection layers:

  Layer 1 — Sliding-Window Anomaly Detection
      N=10 readings, σ-based CRITICAL alert when deviation > 2σ.

  Layer 2 — Velocity-of-Failure Trend Prediction
      N=20 readings, linear regression.  If breach within PREDICTION_ETA
      seconds, emits a PREDICTION alert with ETA and velocity annotations.

  Layer 3 — Event Collapsing / Smart Zone Aggregation
      If ≥ ZONE_SENSOR_MIN sensors in the same Zone breach within
      ZONE_WINDOW_SEC seconds, collapse into a single ZONE_ALARM event
      instead of flooding the feed with individual alerts.

Criticality Score (0–100):
      Blends σ-deviation (40 %), sensor priority (30 %), and rate-of-change
      (30 %) into a single urgency number the UI renders as a bar.

Usage:
      engine = PredictiveHMI.instance()
      result = await engine.process(payload)

      # or via module-level backward-compatible alias:
      result = await process_reading(payload)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import NamedTuple

import numpy as np

from .database import get_db
from .models import Alert, Severity, SensorReading, TelemetryPayload

log = logging.getLogger("pulseguard.engine")

# ── Tuneable constants ────────────────────────────────────────────────────────
WINDOW_ANOMALY:   int   = 10      # readings used for σ-based anomaly check
WINDOW_VELOCITY:  int   = 20      # readings used for linear regression
STD_THRESHOLD:    float = 2.0     # σ multiplier; above this → CRITICAL
PREDICTION_ETA:   float = 30.0    # seconds; if breach within window → PREDICTION
ZONE_SENSOR_MIN:  int   = 3       # min sensors per zone to trigger ZONE_ALARM
ZONE_WINDOW_SEC:  float = 10.0    # time window (s) for zone collapse

# Sensor metadata: (priority 0–10, normal_max for velocity threshold estimate)
SENSOR_META: dict[str, tuple[float, float]] = {
    "temp_sensor_z1":      (10.0, 100.0),
    "temp_sensor_z2":      (10.0, 100.0),
    "temp_sensor_z3":      (10.0, 100.0),
    "pressure_sensor_z1":  ( 8.0, 150.0),
    "pressure_sensor_z2":  ( 8.0, 150.0),
    "pressure_sensor_z3":  ( 8.0, 150.0),
    "vibration_sensor_z1": ( 7.0,  10.0),
    "vibration_sensor_z2": ( 7.0,  10.0),
    "vibration_sensor_z3": ( 7.0,  10.0),
    "flow_sensor_z1":      ( 6.0,  60.0),
    "flow_sensor_z2":      ( 6.0,  60.0),
    "flow_sensor_z3":      ( 6.0,  60.0),
}


class EngineResult(NamedTuple):
    """Composite result returned by PredictiveHMI.process()."""
    reading:    SensorReading
    alert:      Alert | None   # CRITICAL anomaly (Layer 1)
    prediction: Alert | None   # PREDICTION trend  (Layer 2)
    zone_alarm: Alert | None   # ZONE_ALARM event  (Layer 3)


# ─────────────────────────────────────────────────────────────────────────────
class PredictiveHMI:
    """
    Singleton predictive engine — one instance serves the whole application.

    The three detection layers run sequentially per ingested reading.
    Layer 2 is skipped when Layer 1 already fired (already CRITICAL).
    Layer 3 fires independently, always.
    """

    _instance: PredictiveHMI | None = None

    def __init__(self) -> None:
        # Zone collapse buffer: {zone → [(sensor_id, unix_timestamp_float)]}
        self._zone_buffer: dict[str, list[tuple[str, float]]] = defaultdict(list)

    # ── Singleton accessor ────────────────────────────────────────────────────
    @classmethod
    def instance(cls) -> PredictiveHMI:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── DB helpers ────────────────────────────────────────────────────────────
    @staticmethod
    async def _get_recent(
        sensor_id: str, n: int
    ) -> list[tuple[float, datetime]]:
        """Return the last *n* (value, timestamp) pairs, newest-first."""
        db = get_db()
        cursor = (
            db["sensor_readings"]
            .find(
                {"sensor_id": sensor_id},
                {"value": 1, "timestamp": 1, "_id": 0},
            )
            .sort("timestamp", -1)
            .limit(n)
        )
        docs = await cursor.to_list(length=n)
        return [(d["value"], d["timestamp"]) for d in docs]

    # ── Scoring helper ────────────────────────────────────────────────────────
    @staticmethod
    def _criticality_score(deviation: float, priority: float, roc: float) -> float:
        """Blend deviation, sensor priority, and rate-of-change into 0–100."""
        raw = (deviation * 10 * 0.4) + (priority * 0.3) + (min(roc, 30.0) * 0.3)
        return round(min(max(raw, 0.0), 100.0), 2)

    # ── Layer 1 — σ-Anomaly Detection ────────────────────────────────────────
    async def _detect_anomaly(
        self,
        payload: TelemetryPayload,
        priority: float,
        threshold: float,
    ) -> Alert | None:
        """
        Compute mean/σ over WINDOW_ANOMALY recent readings.
        If the new value deviates by more than STD_THRESHOLD σ → CRITICAL.
        """
        recent = await self._get_recent(payload.sensor_id, WINDOW_ANOMALY)
        if len(recent) < 3:
            return None

        values = [v for v, _ in recent]
        arr    = np.array(values, dtype=float)
        mean   = float(np.mean(arr))
        std    = float(np.std(arr))

        if std <= 0:
            return None

        deviation = abs(payload.value - mean) / std
        roc       = abs(payload.value - values[0])          # Δ from last reading
        score     = self._criticality_score(deviation, priority, roc)

        if deviation <= STD_THRESHOLD:
            return None

        alert = Alert(
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
        db = get_db()
        await db["alerts"].insert_one(alert.model_dump())
        log.info("CRITICAL anomaly on %s  score=%.1f", payload.sensor_id, score)
        return alert

    # ── Layer 2 — Velocity-of-Failure Prediction ─────────────────────────────
    async def _predict_velocity(
        self,
        payload: TelemetryPayload,
        threshold: float,
    ) -> Alert | None:
        """
        Fit a linear trend over WINDOW_VELOCITY recent readings.
        If the sensor is rising and will breach `threshold` within
        PREDICTION_ETA seconds, emit a PREDICTION alert with ETA metadata.
        """
        recent = await self._get_recent(payload.sensor_id, WINDOW_VELOCITY)
        if len(recent) < 5:
            return None

        # oldest → newest
        vals  = np.array([v for v, _ in recent[::-1]], dtype=float)
        t_idx = np.arange(len(vals), dtype=float)
        coeffs            = np.polyfit(t_idx, vals, 1)
        velocity_per_tick = float(coeffs[0])   # units per reading-interval

        if velocity_per_tick <= 0:
            return None   # sensor is flat or falling — no imminent breach

        ts_list   = [ts for _, ts in recent[::-1]]
        total_sec = (ts_list[-1] - ts_list[0]).total_seconds()
        if total_sec <= 0:
            return None

        ticks_per_sec    = (len(ts_list) - 1) / total_sec
        velocity_per_sec = velocity_per_tick * ticks_per_sec

        if payload.value >= threshold:
            return None   # already breached

        eta = (threshold - payload.value) / velocity_per_sec
        if not (0 < eta <= PREDICTION_ETA):
            return None

        pred_score = min(100.0, (1 - eta / PREDICTION_ETA) * 100)
        alert = Alert(
            sensor_id=payload.sensor_id,
            severity=Severity.PREDICTION,
            message=(
                f"[PREDICTION] {payload.sensor_id} trending toward "
                f"threshold {threshold:.1f} — breach in {eta:.0f}s "
                f"at +{velocity_per_sec:.3f}/s"
            ),
            criticality_score=round(pred_score, 2),
            value=payload.value,
            zone=payload.zone,
            sector=payload.sector,
            is_prediction=True,
            eta_seconds=round(eta, 1),
            velocity=round(velocity_per_sec, 4),
        )
        db = get_db()
        await db["alerts"].insert_one(alert.model_dump())
        log.info(
            "PREDICTION on %s  eta=%.0fs  vel=%.4f/s",
            payload.sensor_id, eta, velocity_per_sec,
        )
        return alert

    # ── Layer 3 — Event Collapsing / Zone Alarm ───────────────────────────────
    async def _check_zone_alarm(
        self,
        payload: TelemetryPayload,
        anomaly_triggered: bool,
    ) -> Alert | None:
        """
        If `anomaly_triggered` is True, add this sensor to the zone collapse
        buffer.  If ZONE_SENSOR_MIN distinct sensors in the same zone have
        all fired within ZONE_WINDOW_SEC, collapse them into one ZONE_ALARM
        and clear the buffer so it only fires once per event cluster.
        """
        if not anomaly_triggered or not payload.zone:
            return None

        now = datetime.now(timezone.utc).timestamp()
        self._zone_buffer[payload.zone].append((payload.sensor_id, now))

        # Evict stale entries outside the collapse window
        self._zone_buffer[payload.zone] = [
            (sid, ts)
            for sid, ts in self._zone_buffer[payload.zone]
            if now - ts <= ZONE_WINDOW_SEC
        ]

        unique_sensors = list({sid for sid, _ in self._zone_buffer[payload.zone]})
        if len(unique_sensors) < ZONE_SENSOR_MIN:
            return None

        # Clear so the same cluster doesn't fire again immediately
        self._zone_buffer[payload.zone].clear()

        affected = unique_sensors
        summary  = (
            f"Zone {payload.zone}: {len(affected)} sensors breached simultaneously "
            f"({', '.join(affected)})"
        )
        alert = Alert(
            sensor_id=payload.sensor_id,
            severity=Severity.ZONE_ALARM,
            message=f"[ZONE ALARM] {summary}",
            criticality_score=100.0,
            value=payload.value,
            zone=payload.zone,
            sector=payload.sector,
            is_zone_alarm=True,
            affected_sensors=affected,
            zone_summary=summary,
        )
        db = get_db()
        await db["alerts"].insert_one(alert.model_dump())
        log.warning("ZONE_ALARM in %s  sensors=%s", payload.zone, affected)
        return alert

    # ── Public API ────────────────────────────────────────────────────────────
    async def process(self, payload: TelemetryPayload) -> EngineResult:
        """
        Ingest one telemetry reading, persist it, and run all three detection
        layers.  Returns an EngineResult with optional alert, prediction, and
        zone_alarm fields populated.
        """
        db  = get_db()
        now = datetime.now(timezone.utc)

        priority, normal_max = SENSOR_META.get(payload.sensor_id, (5.0, 200.0))
        threshold = payload.threshold or normal_max * 1.15

        # Persist reading
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

        # Layer 1 — Anomaly
        anomaly = await self._detect_anomaly(payload, priority, threshold)

        # Layer 2 — Velocity prediction (skipped when already CRITICAL)
        prediction = (
            None
            if anomaly
            else await self._predict_velocity(payload, threshold)
        )

        # Layer 3 — Zone collapse (fires regardless of other layers)
        zone_alarm = await self._check_zone_alarm(
            payload, anomaly_triggered=anomaly is not None
        )

        return EngineResult(
            reading=reading,
            alert=anomaly,
            prediction=prediction,
            zone_alarm=zone_alarm,
        )

    async def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Mark an alert as acknowledged in MongoDB.
        Returns True if a document was updated, False if not found.
        """
        db     = get_db()
        result = await db["alerts"].update_one(
            {"alert_id": alert_id},
            {"$set": {"acknowledged": True}},
        )
        return result.modified_count > 0

    def zone_health_summary(self) -> dict[str, str]:
        """
        Return a coarse health label for each known zone based on how many
        sensors are currently in the collapse buffer.
        """
        summary: dict[str, str] = {}
        for zone, entries in self._zone_buffer.items():
            unique = len({sid for sid, _ in entries})
            if unique == 0:
                summary[zone] = "ok"
            elif unique < ZONE_SENSOR_MIN:
                summary[zone] = "warning"
            else:
                summary[zone] = "critical"
        return summary


# ── Module-level backward-compatible alias ────────────────────────────────────
async def process_reading(payload: TelemetryPayload) -> EngineResult:
    """Convenience function; delegates to the singleton PredictiveHMI engine."""
    return await PredictiveHMI.instance().process(payload)
