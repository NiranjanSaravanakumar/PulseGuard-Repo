"""
PulseGuard — Pydantic v2 models for validation and MongoDB documents.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Severity(str, Enum):
    INFO       = "INFO"
    WARNING    = "WARNING"
    CRITICAL   = "CRITICAL"
    PREDICTION = "PREDICTION"   # velocity-of-failure forecast
    ZONE_ALARM = "ZONE_ALARM"   # collapsed multi-sensor zone event


class SensorReading(BaseModel):
    sensor_id: str
    value: float
    unit: str = ""
    sector: str = ""
    zone: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class Alert(BaseModel):
    alert_id: str = Field(default_factory=lambda: str(uuid4()))
    sensor_id: str
    severity: Severity
    message: str
    criticality_score: float = 0.0
    value: float
    mean: float = 0.0
    std_dev: float = 0.0
    zone: str = ""
    sector: str = ""
    # Prediction fields
    is_prediction: bool = False
    eta_seconds: float | None = None          # seconds until threshold breach
    velocity: float | None = None             # units per second
    # Zone alarm fields
    is_zone_alarm: bool = False
    affected_sensors: list[str] = Field(default_factory=list)
    zone_summary: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False


class TelemetryPayload(BaseModel):
    """Incoming payload from the simulator via POST /api/v1/telemetry."""
    sensor_id: str
    value: float
    unit: str = ""
    sector: str = ""
    zone: str = ""
    threshold: float | None = None            # simulator-provided critical threshold
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── UI schema with draggable/position support ─────────────────────────────────
class ComponentPosition(BaseModel):
    x: int = 0
    y: int = 0
    w: int = 2
    h: int = 2


class UIComponent(BaseModel):
    type: str
    source: str | None = None
    sensor: str | None = None
    label: str | None = None
    size: str = "medium"
    chart_type: str | None = None
    draggable: bool = True
    position: ComponentPosition = Field(default_factory=ComponentPosition)


class UISchema(BaseModel):
    role: str
    layout: str = "grid"
    theme: str = "dark"
    components: list[UIComponent] = Field(default_factory=list)

    theme: str = "dark"
    components: list[UIComponent] = Field(default_factory=list)
