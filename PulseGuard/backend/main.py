"""
PulseGuard — FastAPI Backend
• WebSocket rooms per user role (operator / engineer)
• /config  → metadata-driven UI-Schema per role
• /alerts  → recent alert history
• /ingest  → HTTP sensor ingestion (WebSocket preferred)
"""
import json
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

from ai_engine import AIEngine, SensorReading

# ──────────────────────────────────────────────────────────────────────────────
# App init
# ──────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="PulseGuard IIoT", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME   = "pulseguard"


# ──────────────────────────────────────────────────────────────────────────────
# Startup / Shutdown
# ──────────────────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def _startup():
    app.state.mongo     = AsyncIOMotorClient(MONGO_URL)
    app.state.db        = app.state.mongo[DB_NAME]
    app.state.ai_engine = AIEngine()


@app.on_event("shutdown")
async def _shutdown():
    app.state.mongo.close()


# ──────────────────────────────────────────────────────────────────────────────
# WebSocket Room Manager
# ──────────────────────────────────────────────────────────────────────────────
class RoomManager:
    """
    Maintains per-role WebSocket rooms.

    Operators receive only CRITICAL alerts.
    Engineers receive raw readings + all alert levels.
    """

    VALID_ROLES = {"operator", "engineer"}

    def __init__(self):
        self._rooms: dict[str, set[WebSocket]] = {r: set() for r in self.VALID_ROLES}

    async def connect(self, ws: WebSocket, role: str) -> str:
        await ws.accept()
        safe_role = role if role in self.VALID_ROLES else "operator"
        self._rooms[safe_role].add(ws)
        return safe_role

    def disconnect(self, ws: WebSocket, role: str) -> None:
        self._rooms.get(role, set()).discard(ws)

    async def broadcast(self, role: str, payload: dict) -> None:
        dead: set[WebSocket] = set()
        for ws in list(self._rooms.get(role, set())):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.add(ws)
        self._rooms[role] -= dead

    async def broadcast_all(self, payload: dict) -> None:
        for role in self.VALID_ROLES:
            await self.broadcast(role, payload)


manager = RoomManager()


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic models
# ──────────────────────────────────────────────────────────────────────────────
class SensorPayload(BaseModel):
    sensor_id: str
    sector:    str
    value:     float
    timestamp: Optional[float] = None


# ──────────────────────────────────────────────────────────────────────────────
# REST Endpoints
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "app": "PulseGuard IIoT"}


@app.get("/config")
async def get_ui_config(role: str = Query(default="operator")):
    """
    Returns the metadata-driven UI-Schema for the requesting user role.

    Example response:
    {
        "role": "operator",
        "layout": "grid",
        "components": [
            {"type": "chart", "sensor": "temp-01", "size": "large", "title": "Temperature"},
            ...
        ]
    }
    """
    db  = app.state.db
    doc = await db.ui_schemas.find_one({"role": role}, {"_id": 0})
    return doc if doc else _default_schema(role)


@app.get("/alerts")
async def get_recent_alerts(limit: int = Query(default=50, le=200)):
    """Return the most recent alerts stored in MongoDB."""
    db     = app.state.db
    cursor = db.alerts.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
    return await cursor.to_list(length=limit)


@app.post("/ingest")
async def ingest_reading(payload: SensorPayload):
    """HTTP fallback for sensor data ingestion (WebSocket preferred)."""
    import time
    reading = SensorReading(
        sensor_id = payload.sensor_id,
        sector    = payload.sector,
        value     = payload.value,
        timestamp = payload.timestamp or time.time(),
    )
    alert = app.state.ai_engine.process_reading(reading)
    if alert:
        doc = {**alert.__dict__, "created_at": _utcnow()}
        await app.state.db.alerts.insert_one(doc)
        doc.pop("_id", None)
        await manager.broadcast_all({"type": "alert", "data": doc})
        return {"status": "alert_raised", "score": alert.criticality_score}
    return {"status": "nominal"}


# ──────────────────────────────────────────────────────────────────────────────
# WebSocket Endpoint
# ──────────────────────────────────────────────────────────────────────────────
@app.websocket("/ws/{role}")
async def websocket_endpoint(ws: WebSocket, role: str):
    room = await manager.connect(ws, role)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            if msg.get("type") != "sensor_data":
                continue

            import time
            d       = msg.get("data", {})
            reading = SensorReading(
                sensor_id = str(d.get("sensor_id", "unknown")),
                sector    = str(d.get("sector", "default")),
                value     = float(d.get("value", 0.0)),
                timestamp = float(d.get("timestamp", time.time())),
            )

            # Engineers always get raw readings for trend charts
            await manager.broadcast(
                "engineer",
                {"type": "sensor_reading", "data": reading.__dict__},
            )

            alert = app.state.ai_engine.process_reading(reading)
            if alert:
                doc = {**alert.__dict__, "created_at": _utcnow()}
                await app.state.db.alerts.insert_one({**doc})
                doc.pop("_id", None)

                if alert.severity == "CRITICAL":
                    # Critical alerts → all roles
                    await manager.broadcast_all({"type": "alert", "data": doc})
                else:
                    # Warning / Info → engineers only
                    await manager.broadcast("engineer", {"type": "alert", "data": doc})

    except WebSocketDisconnect:
        manager.disconnect(ws, room)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _default_schema(role: str) -> dict:
    """Fallback schema when MongoDB has no document for the requested role."""
    if role == "engineer":
        return {
            "role":   "engineer",
            "layout": "grid",
            "theme":  "dark",
            "components": [
                {"type": "chart",       "sensor": "temp-01",     "size": "large",  "title": "Temperature Zone A"},
                {"type": "chart",       "sensor": "pressure-01", "size": "large",  "title": "Pressure Line 1"},
                {"type": "chart",       "sensor": "vibration-01","size": "medium", "title": "Vibration Motor 3"},
                {"type": "chart",       "sensor": "temp-02",     "size": "medium", "title": "Temperature Zone B"},
                {"type": "status_card", "sensor": "flow-01",     "size": "small",  "title": "Flow Rate"},
                {"type": "alert_feed",                           "size": "large",  "title": "Intelligence Feed"},
            ],
        }
    return {
        "role":   "operator",
        "layout": "grid",
        "theme":  "light",
        "components": [
            {"type": "chart",       "sensor": "temp-01",     "size": "large",  "title": "Temperature Overview"},
            {"type": "status_card", "sensor": "pressure-01", "size": "medium", "title": "System Pressure"},
            {"type": "status_card", "sensor": "flow-01",     "size": "medium", "title": "Flow Rate"},
            {"type": "alert_feed",                           "size": "large",  "title": "Active Alerts"},
        ],
    }
