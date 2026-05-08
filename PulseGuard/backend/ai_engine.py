"""
PulseGuard — AI Prioritization Engine
Criticality Score = (Value Deviation * 0.4) + (Sensor Priority * 0.3) + (Rate of Change * 0.3)
Alert Debouncing: 10 alerts from same sector in <5s → Aggregated Event
"""
import uuid
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

# ---------------------------------------------------------------------------
# Sensor priority table (0‒1). Higher = more critical.
# ---------------------------------------------------------------------------
SENSOR_PRIORITIES: dict[str, float] = {
    "temp":      0.90,
    "pressure":  0.85,
    "vibration": 0.75,
    "flow":      0.70,
    "humidity":  0.55,
}


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------
@dataclass
class SensorReading:
    sensor_id: str
    sector:    str
    value:     float
    timestamp: float = field(default_factory=time.time)


@dataclass
class Alert:
    alert_id:          str
    sensor_id:         str
    sector:            str
    value:             float
    criticality_score: float
    severity:          str          # "INFO" | "WARNING" | "CRITICAL"
    message:           str
    timestamp:         float = field(default_factory=time.time)
    is_aggregated:     bool  = False
    aggregated_count:  int   = 1
    summary:           Optional[str] = None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class AIEngine:
    """Stateful AI engine — keeps per‑sensor history for scoring."""

    def __init__(self, history_window: int = 100):
        self.history_window = history_window
        # sensor_id -> rolling list of recent values
        self._history: dict[str, list[float]] = defaultdict(list)
        # sector -> [(timestamp, raw_alert_dict)]
        self._debounce_buffer: dict[str, list[tuple[float, dict]]] = defaultdict(list)
        self._debounce_window:    float = 5.0   # seconds
        self._debounce_threshold: int   = 10    # alerts before aggregation

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #
    def _sensor_priority(self, sensor_id: str) -> float:
        lower = sensor_id.lower()
        for key, priority in SENSOR_PRIORITIES.items():
            if key in lower:
                return priority
        return 0.50  # default

    def _push_history(self, sensor_id: str, value: float) -> None:
        buf = self._history[sensor_id]
        buf.append(value)
        if len(buf) > self.history_window:
            buf.pop(0)

    def _value_deviation(self, sensor_id: str, value: float) -> float:
        """Normalised z‑score deviation, clamped to [0, 1] (3σ = max)."""
        hist = self._history[sensor_id]
        if len(hist) < 2:
            return 0.0
        mean = float(np.mean(hist))
        std  = float(np.std(hist))
        if std < 1e-9:
            return 0.0
        z = abs(value - mean) / std
        return min(z / 3.0, 1.0)

    def _rate_of_change(self, sensor_id: str) -> float:
        """Relative change between the last two readings, clamped to [0, 1]."""
        hist = self._history[sensor_id]
        if len(hist) < 2:
            return 0.0
        prev = hist[-2]
        curr = hist[-1]
        roc  = abs(curr - prev) / (abs(prev) + 1e-9)
        return min(roc, 1.0)

    @staticmethod
    def _severity(score: float) -> str:
        if score >= 75:
            return "CRITICAL"
        if score >= 45:
            return "WARNING"
        return "INFO"

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #
    def calculate_criticality_score(self, sensor_id: str, value: float) -> float:
        """
        Score (0–100):
            (deviation * 0.4) + (priority * 0.3) + (roc * 0.3)  × 100
        """
        deviation = self._value_deviation(sensor_id, value)
        priority  = self._sensor_priority(sensor_id)
        roc       = self._rate_of_change(sensor_id)
        raw       = (deviation * 0.4) + (priority * 0.3) + (roc * 0.3)
        return round(min(raw * 100.0, 100.0), 2)

    def process_reading(self, reading: SensorReading) -> Optional[Alert]:
        """
        Ingest a sensor reading, update history, compute score.
        Returns an Alert (possibly aggregated) or None for nominal INFO.
        """
        self._push_history(reading.sensor_id, reading.value)
        score    = self.calculate_criticality_score(reading.sensor_id, reading.value)
        severity = self._severity(score)

        if severity == "INFO":
            return None

        raw = {
            "sensor_id": reading.sensor_id,
            "sector":    reading.sector,
            "value":     reading.value,
            "score":     score,
            "severity":  severity,
            "timestamp": reading.timestamp,
        }
        return self._debounce(raw)

    def _debounce(self, alert_data: dict) -> Alert:
        """
        If ≥ DEBOUNCE_THRESHOLD alerts from the same sector arrive within
        DEBOUNCE_WINDOW seconds, collapse them into one Aggregated Event.
        """
        sector = alert_data["sector"]
        now    = alert_data["timestamp"]

        # Evict stale entries
        self._debounce_buffer[sector] = [
            (ts, a) for ts, a in self._debounce_buffer[sector]
            if now - ts < self._debounce_window
        ]
        self._debounce_buffer[sector].append((now, alert_data))
        count = len(self._debounce_buffer[sector])

        if count >= self._debounce_threshold:
            # ── Aggregated Event ─────────────────────────────────────────
            entries    = self._debounce_buffer[sector]
            scores     = [a["score"] for _, a in entries]
            sensors    = list({a["sensor_id"] for _, a in entries})
            peak_score = max(scores)

            summary = (
                f"AI Aggregated: {count} alerts fired from sector '{sector}' "
                f"within {self._debounce_window:.0f}s. "
                f"Affected sensors: {', '.join(sensors[:6])}. "
                f"Peak Criticality Score: {peak_score:.1f} / 100. "
                "Recommend immediate investigation."
            )
            self._debounce_buffer[sector].clear()

            return Alert(
                alert_id          = str(uuid.uuid4()),
                sensor_id         = sensors[0],
                sector            = sector,
                value             = alert_data["value"],
                criticality_score = peak_score,
                severity          = "CRITICAL",
                message           = f"Alert storm detected in sector {sector}",
                is_aggregated     = True,
                aggregated_count  = count,
                summary           = summary,
            )

        # ── Single Alert ─────────────────────────────────────────────────
        return Alert(
            alert_id          = str(uuid.uuid4()),
            sensor_id         = alert_data["sensor_id"],
            sector            = alert_data["sector"],
            value             = alert_data["value"],
            criticality_score = alert_data["score"],
            severity          = alert_data["severity"],
            message           = (
                f"{alert_data['sensor_id']} reading {alert_data['value']:.3f} — "
                f"Criticality {alert_data['score']:.1f}/100"
            ),
        )
