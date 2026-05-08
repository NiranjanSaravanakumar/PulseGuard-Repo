"""
PulseGuard — FastAPI Backend v3  (Digital Twin Command Center)
──────────────────────────────────────────────────────────────
POST /api/v1/telemetry      — ingest sensor telemetry from simulator
GET  /api/v1/ui-config      — metadata-driven UI schema per role
PUT  /api/v1/ui-config/{role} — persist updated schema (position/draggable)
GET  /api/v1/alerts         — recent alert history
GET  /api/v1/sensors/status — latest value per sensor (for Digital Twin)
GET  /health                — liveness probe
WS   /ws/{role}             — real-time broadcast (role-filtered)
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .database import close_connection, get_db
from .engine import EngineResult, process_reading
from .models import Severity, TelemetryPayload, UISchema


# ── Global WebSocket Manager (role rooms) ─────────────────────────────────────
class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, ws: WebSocket, room: str) -> None:
        await ws.accept()
        self._rooms.setdefault(room, []).append(ws)

    def disconnect(self, ws: WebSocket, room: str) -> None:
        conns = self._rooms.get(room, [])
        if ws in conns:
            conns.remove(ws)

    async def _send_room(self, data: dict[str, Any], room: str) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._rooms.get(room, [])):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, room)

    async def broadcast_all(self, data: dict[str, Any]) -> None:
        for room in list(self._rooms):
            await self._send_room(data, room)

    async def broadcast_engineers(self, data: dict[str, Any]) -> None:
        """Raw telemetry — sent to engineer + admin only."""
        for role in ("engineer", "admin"):
            await self._send_room(data, role)

    async def broadcast_alert(self, alert_data: dict[str, Any]) -> None:
        """Alerts go to every role."""
        await self.broadcast_all(alert_data)


manager = ConnectionManager()


# ── Default UI Schemas ────────────────────────────────────────────────────────
_OPERATOR_SCHEMA = {
    "role": "operator",
    "layout": "grid",
    "theme": "dark",
    "components": [
        {"type": "digital_twin",  "label": "Factory Floor",           "size": "large",  "draggable": True,  "position": {"x": 0, "y": 0, "w": 4, "h": 3}},
        {"type": "alert_feed",    "label": "Active Alerts",           "size": "large",  "draggable": True,  "position": {"x": 0, "y": 3, "w": 2, "h": 4}},
        {"type": "status_card",   "source": "temp_sensor_z1",         "label": "Temp Z1",    "size": "small", "draggable": True, "position": {"x": 2, "y": 3, "w": 1, "h": 2}},
        {"type": "status_card",   "source": "pressure_sensor_z1",     "label": "Press Z1",   "size": "small", "draggable": True, "position": {"x": 3, "y": 3, "w": 1, "h": 2}},
        {"type": "line_chart",    "source": "temp_sensor_z1",         "label": "Temperature Z1", "size": "medium", "draggable": True, "position": {"x": 2, "y": 5, "w": 2, "h": 2}},
    ],
}

_ENGINEER_SCHEMA = {
    "role": "engineer",
    "layout": "grid",
    "theme": "dark",
    "components": [
        {"type": "digital_twin",    "label": "Digital Twin",            "size": "large",  "draggable": True, "position": {"x": 0, "y": 0, "w": 4, "h": 3}},
        {"type": "alert_feed",      "label": "Intelligence Feed",       "size": "large",  "draggable": True, "position": {"x": 0, "y": 3, "w": 2, "h": 4}},
        {"type": "radial_gauge",    "source": "temp_sensor_z1",         "label": "Temp Z1",      "size": "small", "draggable": True, "position": {"x": 2, "y": 3, "w": 1, "h": 2}},
        {"type": "radial_gauge",    "source": "pressure_sensor_z1",     "label": "Press Z1",     "size": "small", "draggable": True, "position": {"x": 3, "y": 3, "w": 1, "h": 2}},
        {"type": "radial_gauge",    "source": "vibration_sensor_z2",    "label": "Vib Z2",       "size": "small", "draggable": True, "position": {"x": 2, "y": 5, "w": 1, "h": 2}},
        {"type": "radial_gauge",    "source": "flow_sensor_z3",         "label": "Flow Z3",      "size": "small", "draggable": True, "position": {"x": 3, "y": 5, "w": 1, "h": 2}},
        {"type": "line_chart",      "source": "temp_sensor_z1",         "label": "Temp Z1",      "size": "medium", "draggable": True, "position": {"x": 0, "y": 7, "w": 2, "h": 2}},
        {"type": "area_chart",      "source": "pressure_sensor_z2",     "label": "Press Z2",     "size": "medium", "draggable": True, "position": {"x": 2, "y": 7, "w": 2, "h": 2}},
        {"type": "bar_chart",       "source": "vibration_sensor_z3",    "label": "Vib Z3",       "size": "medium", "draggable": True, "position": {"x": 0, "y": 9, "w": 2, "h": 2}},
        {"type": "line_chart",      "source": "flow_sensor_z1",         "label": "Flow Z1",      "size": "medium", "draggable": True, "position": {"x": 2, "y": 9, "w": 2, "h": 2}},
    ],
}

_ADMIN_SCHEMA = {
    "role": "admin",
    "layout": "grid",
    "theme": "dark",
    "components": [
        {"type": "digital_twin",  "label": "Full Factory View",       "size": "large",  "draggable": True, "position": {"x": 0, "y": 0, "w": 4, "h": 4}},
        {"type": "alert_feed",    "label": "All Events",              "size": "large",  "draggable": True, "position": {"x": 0, "y": 4, "w": 4, "h": 3}},
        {"type": "line_chart",    "source": "temp_sensor_z1",         "label": "Temp Z1",  "size": "medium", "draggable": True, "position": {"x": 0, "y": 7, "w": 2, "h": 2}},
        {"type": "line_chart",    "source": "temp_sensor_z2",         "label": "Temp Z2",  "size": "medium", "draggable": True, "position": {"x": 2, "y": 7, "w": 2, "h": 2}},
        {"type": "area_chart",    "source": "pressure_sensor_z1",     "label": "Press Z1", "size": "medium", "draggable": True, "position": {"x": 0, "y": 9, "w": 2, "h": 2}},
        {"type": "area_chart",    "source": "pressure_sensor_z3",     "label": "Press Z3", "size": "medium", "draggable": True, "position": {"x": 2, "y": 9, "w": 2, "h": 2}},
    ],
}


# ── App lifecycle ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_db()
    if await db["ui_schemas"].count_documents({}) == 0:
        await db["ui_schemas"].insert_many(
            [_OPERATOR_SCHEMA, _ENGINEER_SCHEMA, _ADMIN_SCHEMA]
        )
    # Indexes for performance
    await db["sensor_readings"].create_index([("sensor_id", 1), ("timestamp", -1)])
    await db["alerts"].create_index([("timestamp", -1)])
    yield
    await close_connection()


app = FastAPI(title="PulseGuard IIoT v3", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REST: Telemetry ingestion ─────────────────────────────────────────────────
@app.post("/api/v1/telemetry", status_code=202)
async def ingest_telemetry(payload: TelemetryPayload):
    result: EngineResult = await process_reading(payload)

    # ── Broadcast raw reading to engineers / admins only ─────────────────────
    await manager.broadcast_engineers({
        "type": "sensor_reading",
        "data": {
            "sensor_id": result.reading.sensor_id,
            "value":     result.reading.value,
            "unit":      result.reading.unit,
            "sector":    result.reading.sector,
            "zone":      result.reading.zone,
            "timestamp": result.reading.timestamp.isoformat(),
        },
    })

    # ── Broadcast sensor_ping to ALL roles (drives Digital Twin dots) ─────────
    await manager.broadcast_all({
        "type": "sensor_ping",
        "data": {
            "sensor_id": result.reading.sensor_id,
            "zone":      result.reading.zone,
            "value":     result.reading.value,
            "status": (
                "critical"    if result.alert else
                "warning"     if result.prediction else
                "ok"
            ),
        },
    })

    # ── Broadcast alerts (all types) to everyone ──────────────────────────────
    alerts_fired = []
    for alert in (result.alert, result.prediction, result.zone_alarm):
        if alert:
            # Operators get summary-only for PREDICTION; full for CRITICAL/ZONE
            op_message = alert.zone_summary or alert.message
            if alert.severity == Severity.PREDICTION:
                op_payload = {
                    "type": "alert",
                    "data": {**alert.model_dump(mode="json"), "message": op_message},
                }
            else:
                op_payload = {"type": "alert", "data": alert.model_dump(mode="json")}

            await manager.broadcast_alert(op_payload)
            alerts_fired.append(alert.severity)

    return {
        "status": "accepted",
        "alerts": [s.value for s in alerts_fired],
    }


# ── REST: UI Config ───────────────────────────────────────────────────────────
@app.get("/api/v1/ui-config")
async def get_ui_config(role: str = Query("operator")):
    db  = get_db()
    doc = await db["ui_schemas"].find_one({"role": role}, {"_id": 0})
    if not doc:
        return {"role": role, "layout": "grid", "theme": "dark", "components": []}
    return doc


@app.put("/api/v1/ui-config/{role}", status_code=204)
async def save_ui_config(role: str, schema: UISchema):
    """Persist a user-modified layout (draggable positions) back to MongoDB."""
    db = get_db()
    await db["ui_schemas"].replace_one(
        {"role": role},
        schema.model_dump(),
        upsert=True,
    )


# ── REST: Alerts history ──────────────────────────────────────────────────────
@app.get("/api/v1/alerts")
async def get_alerts(limit: int = Query(50, le=200)):
    db     = get_db()
    cursor = db["alerts"].find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
    return await cursor.to_list(length=limit)


# ── REST: Sensor status snapshot (for Digital Twin init) ─────────────────────
@app.get("/api/v1/sensors/status")
async def get_sensor_status():
    """Returns the latest reading for every known sensor."""
    db      = get_db()
    pipeline = [
        {"$sort": {"timestamp": -1}},
        {"$group": {"_id": "$sensor_id", "latest": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$latest"}},
        {"$project": {"_id": 0}},
    ]
    docs = await db["sensor_readings"].aggregate(pipeline).to_list(length=100)
    return docs


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


# ── WebSocket ─────────────────────────────────────────────────────────────────
@app.websocket("/ws/{role}")
async def websocket_endpoint(ws: WebSocket, role: str):
    await manager.connect(ws, role)
    try:
        while True:
            await ws.receive_text()   # keep-alive; data flows server→client
    except WebSocketDisconnect:
        manager.disconnect(ws, role)
    except Exception:
        manager.disconnect(ws, role)



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
