"""
PulseGuard — Pydantic v2 models for validation and MongoDB documents.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class SensorReading(BaseModel):
    sensor_id: str
    value: float
    unit: str = ""
    sector: str = ""
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
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False


class TelemetryPayload(BaseModel):
    """Incoming payload from the simulator via POST /api/v1/telemetry."""
    sensor_id: str
    value: float
    unit: str = ""
    sector: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class UIComponent(BaseModel):
    type: str
    source: str | None = None
    sensor: str | None = None
    label: str | None = None
    size: str = "medium"
    chart_type: str | None = None


class UISchema(BaseModel):
    role: str
    layout: str = "grid"
    theme: str = "dark"
    components: list[UIComponent] = Field(default_factory=list)
