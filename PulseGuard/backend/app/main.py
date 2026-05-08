"""
PulseGuard — FastAPI Backend v2
────────────────────────────────
POST /api/v1/telemetry   — ingest sensor readings from simulator
GET  /api/v1/ui-config   — metadata-driven UI schema per role
GET  /api/v1/alerts      — recent alert history
GET  /health             — liveness probe
WS   /ws/{role}          — real-time broadcast to HMI clients
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .database import close_connection, get_db
from .engine import process_reading
from .models import TelemetryPayload


# ── Global WebSocket Manager ─────────────────────────────────────────────────
class ConnectionManager:
    """Routes messages to per-role rooms; silently drops dead connections."""

    def __init__(self) -> None:
        self._rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, ws: WebSocket, room: str) -> None:
        await ws.accept()
        self._rooms.setdefault(room, []).append(ws)

    def disconnect(self, ws: WebSocket, room: str) -> None:
        conns = self._rooms.get(room, [])
        if ws in conns:
            conns.remove(ws)

    async def broadcast(self, data: dict[str, Any], room: str | None = None) -> None:
        """Broadcast to a specific room or all rooms when room is None."""
        targets: list[tuple[WebSocket, str]] = []
        if room:
            for ws in list(self._rooms.get(room, [])):
                targets.append((ws, room))
        else:
            for r, conns in self._rooms.items():
                for ws in list(conns):
                    targets.append((ws, r))

        dead: list[tuple[WebSocket, str]] = []
        for ws, r in targets:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append((ws, r))

        for ws, r in dead:
            self.disconnect(ws, r)


manager = ConnectionManager()


# ── Default UI schemas seeded on first start ─────────────────────────────────
_DEFAULT_SCHEMAS = [
    {
        "role": "operator",
        "layout": "grid",
        "theme": "dark",
        "components": [
            {"type": "alert_feed",  "label": "Active Alerts",        "size": "large"},
            {"type": "status_card", "source": "temp_sensor_01",       "label": "Temperature",  "size": "medium"},
            {"type": "status_card", "source": "pressure_sensor_01",   "label": "Pressure",     "size": "medium"},
            {"type": "line_chart",  "source": "temp_sensor_01",       "label": "Temperature",  "size": "large"},
            {"type": "area_chart",  "source": "pressure_sensor_01",   "label": "Pressure",     "size": "large"},
        ],
    },
    {
        "role": "engineer",
        "layout": "grid",
        "theme": "dark",
        "components": [
            {"type": "alert_feed",    "label": "Intelligence Feed",      "size": "large"},
            {"type": "radial_gauge",  "source": "temp_sensor_01",        "label": "Temperature",  "size": "small"},
            {"type": "radial_gauge",  "source": "pressure_sensor_01",    "label": "Pressure",     "size": "small"},
            {"type": "radial_gauge",  "source": "vibration_sensor_01",   "label": "Vibration",    "size": "small"},
            {"type": "radial_gauge",  "source": "flow_sensor_01",        "label": "Flow",         "size": "small"},
            {"type": "line_chart",    "source": "temp_sensor_01",        "label": "Temperature",  "size": "medium"},
            {"type": "area_chart",    "source": "pressure_sensor_01",    "label": "Pressure",     "size": "medium"},
            {"type": "bar_chart",     "source": "vibration_sensor_01",   "label": "Vibration",    "size": "medium"},
            {"type": "line_chart",    "source": "flow_sensor_01",        "label": "Coolant Flow", "size": "medium"},
        ],
    },
]


# ── App lifecycle ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_db()
    if await db["ui_schemas"].count_documents({}) == 0:
        await db["ui_schemas"].insert_many(_DEFAULT_SCHEMAS)
    yield
    await close_connection()


app = FastAPI(title="PulseGuard IIoT v2", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REST Routes ───────────────────────────────────────────────────────────────
@app.post("/api/v1/telemetry", status_code=202)
async def ingest_telemetry(payload: TelemetryPayload):
    reading, alert = await process_reading(payload)

    # Broadcast live sensor reading to all HMI clients
    await manager.broadcast({
        "type": "sensor_reading",
        "data": {
            "sensor_id": reading.sensor_id,
            "value":     reading.value,
            "unit":      reading.unit,
            "sector":    reading.sector,
            "timestamp": reading.timestamp.isoformat(),
        },
    })

    # Broadcast alert if one was generated
    if alert:
        await manager.broadcast({
            "type": "alert",
            "data": alert.model_dump(mode="json"),
        })

    return {"status": "accepted", "alert_generated": alert is not None}


@app.get("/api/v1/ui-config")
async def get_ui_config(role: str = Query("operator")):
    db = get_db()
    doc = await db["ui_schemas"].find_one({"role": role}, {"_id": 0})
    if not doc:
        return {"role": role, "layout": "grid", "theme": "dark", "components": []}
    return doc


@app.get("/api/v1/alerts")
async def get_alerts(limit: int = Query(50, le=200)):
    db = get_db()
    cursor = db["alerts"].find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
    return await cursor.to_list(length=limit)


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


# ── WebSocket Endpoint ────────────────────────────────────────────────────────
@app.websocket("/ws/{role}")
async def websocket_endpoint(ws: WebSocket, role: str):
    await manager.connect(ws, role)
    try:
        while True:
            # Keep connection alive — messages flow server→client only
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws, role)
    except Exception:
        manager.disconnect(ws, role)
