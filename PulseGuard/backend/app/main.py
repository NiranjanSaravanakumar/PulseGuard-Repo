"""
PulseGuard � FastAPI Backend  v4  (Digital Twin Command Center)
===============================================================================
Endpoints
---------
POST  /api/v1/telemetry              ingest sensor data, run AI engine, broadcast
GET   /api/v1/ui-config?role=        role-specific layout schema
PUT   /api/v1/ui-config/{role}       persist draggable layout changes
GET   /api/v1/alerts                 recent alert history
PATCH /api/v1/alerts/{id}/acknowledge mark alert acknowledged
GET   /api/v1/sensors/status         latest reading per sensor (Digital Twin init)
GET   /api/v1/zones/health           coarse zone health from engine collapse buffer
GET   /health                        liveness probe
WS    /ws/{role}                     real-time broadcast (role-filtered rooms)
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .ai_engine import EngineResult, PredictiveHMI, process_reading
from .database import close_connection, get_db
from .models import Severity, TelemetryPayload, UISchema


# -- WebSocket Manager (role-based rooms) -------------------------------------
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
        for role in ("engineer", "admin"):
            await self._send_room(data, role)

    async def broadcast_alert(self, data: dict[str, Any]) -> None:
        await self.broadcast_all(data)


manager = ConnectionManager()


# -- Default UI Schemas --------------------------------------------------------
_OPERATOR_SCHEMA = {
    "role": "operator", "layout": "grid", "theme": "dark",
    "components": [
        {"type": "digital_twin",  "label": "Factory Floor",       "size": "large",  "draggable": True, "position": {"x": 0, "y": 0, "w": 4, "h": 3}},
        {"type": "alert_feed",    "label": "Active Alerts",        "size": "large",  "draggable": True, "position": {"x": 0, "y": 3, "w": 2, "h": 4}},
        {"type": "status_card",   "source": "temp_sensor_z1",      "label": "Temp Z1",   "size": "small",  "draggable": True, "position": {"x": 2, "y": 3, "w": 1, "h": 2}},
        {"type": "status_card",   "source": "pressure_sensor_z1",  "label": "Press Z1",  "size": "small",  "draggable": True, "position": {"x": 3, "y": 3, "w": 1, "h": 2}},
        {"type": "line_chart",    "source": "temp_sensor_z1",      "label": "Temperature Z1", "size": "medium", "draggable": True, "position": {"x": 2, "y": 5, "w": 2, "h": 2}},
    ],
}

_ENGINEER_SCHEMA = {
    "role": "engineer", "layout": "grid", "theme": "dark",
    "components": [
        {"type": "digital_twin",    "label": "Digital Twin",           "size": "large",  "draggable": True, "position": {"x": 0, "y": 0, "w": 4, "h": 3}},
        {"type": "alert_feed",      "label": "Intelligence Feed",      "size": "large",  "draggable": True, "position": {"x": 0, "y": 3, "w": 2, "h": 4}},
        {"type": "radial_gauge",    "source": "temp_sensor_z1",        "label": "Temp Z1",   "size": "small",  "draggable": True, "position": {"x": 2, "y": 3, "w": 1, "h": 2}},
        {"type": "radial_gauge",    "source": "pressure_sensor_z1",    "label": "Press Z1",  "size": "small",  "draggable": True, "position": {"x": 3, "y": 3, "w": 1, "h": 2}},
        {"type": "radial_gauge",    "source": "vibration_sensor_z2",   "label": "Vib Z2",    "size": "small",  "draggable": True, "position": {"x": 2, "y": 5, "w": 1, "h": 2}},
        {"type": "radial_gauge",    "source": "flow_sensor_z3",        "label": "Flow Z3",   "size": "small",  "draggable": True, "position": {"x": 3, "y": 5, "w": 1, "h": 2}},
        {"type": "line_chart",      "source": "temp_sensor_z1",        "label": "Temp Z1",   "size": "medium", "draggable": True, "position": {"x": 0, "y": 7, "w": 2, "h": 2}},
        {"type": "area_chart",      "source": "pressure_sensor_z2",    "label": "Press Z2",  "size": "medium", "draggable": True, "position": {"x": 2, "y": 7, "w": 2, "h": 2}},
        {"type": "bar_chart",       "source": "vibration_sensor_z3",   "label": "Vib Z3",    "size": "medium", "draggable": True, "position": {"x": 0, "y": 9, "w": 2, "h": 2}},
        {"type": "line_chart",      "source": "flow_sensor_z1",        "label": "Flow Z1",   "size": "medium", "draggable": True, "position": {"x": 2, "y": 9, "w": 2, "h": 2}},
    ],
}

_ADMIN_SCHEMA = {
    "role": "admin", "layout": "grid", "theme": "dark",
    "components": [
        {"type": "digital_twin",  "label": "Full Factory View",     "size": "large",  "draggable": True, "position": {"x": 0, "y": 0, "w": 4, "h": 4}},
        {"type": "alert_feed",    "label": "All Events",            "size": "large",  "draggable": True, "position": {"x": 0, "y": 4, "w": 4, "h": 3}},
        {"type": "line_chart",    "source": "temp_sensor_z1",       "label": "Temp Z1",   "size": "medium", "draggable": True, "position": {"x": 0, "y": 7, "w": 2, "h": 2}},
        {"type": "line_chart",    "source": "temp_sensor_z2",       "label": "Temp Z2",   "size": "medium", "draggable": True, "position": {"x": 2, "y": 7, "w": 2, "h": 2}},
        {"type": "area_chart",    "source": "pressure_sensor_z1",   "label": "Press Z1",  "size": "medium", "draggable": True, "position": {"x": 0, "y": 9, "w": 2, "h": 2}},
        {"type": "area_chart",    "source": "pressure_sensor_z3",   "label": "Press Z3",  "size": "medium", "draggable": True, "position": {"x": 2, "y": 9, "w": 2, "h": 2}},
    ],
}


# -- Lifespan ------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_db()
    if await db["ui_schemas"].count_documents({}) == 0:
        await db["ui_schemas"].insert_many(
            [_OPERATOR_SCHEMA, _ENGINEER_SCHEMA, _ADMIN_SCHEMA]
        )
    await db["sensor_readings"].create_index([("sensor_id", 1), ("timestamp", -1)])
    await db["alerts"].create_index([("timestamp", -1)])
    await db["alerts"].create_index([("alert_id", 1)], unique=True, sparse=True)
    yield
    await close_connection()


# -- FastAPI app ---------------------------------------------------------------
app = FastAPI(
    title="PulseGuard IIoT",
    version="4.0.0",
    description="Digital Twin Command Center -- predictive intelligence for industrial systems",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- Telemetry ingestion -------------------------------------------------------
@app.post("/api/v1/telemetry", status_code=202)
async def ingest_telemetry(payload: TelemetryPayload):
    result: EngineResult = await process_reading(payload)

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

    await manager.broadcast_all({
        "type": "sensor_ping",
        "data": {
            "sensor_id": result.reading.sensor_id,
            "zone":      result.reading.zone,
            "value":     result.reading.value,
            "status": (
                "critical" if result.alert else
                "warning"  if result.prediction else
                "ok"
            ),
        },
    })

    alerts_fired = []
    for alert in (result.alert, result.prediction, result.zone_alarm):
        if alert is None:
            continue
        alert_payload: dict = alert.model_dump(mode="json")
        if alert.severity == Severity.PREDICTION:
            alert_payload["message"] = alert.zone_summary or alert.message
        await manager.broadcast_alert({"type": "alert", "data": alert_payload})
        alerts_fired.append(alert.severity)

    return {"status": "accepted", "alerts": [s.value for s in alerts_fired]}


# -- UI config ----------------------------------------------------------------
@app.get("/api/v1/ui-config")
async def get_ui_config(role: str = Query("operator")):
    db  = get_db()
    doc = await db["ui_schemas"].find_one({"role": role}, {"_id": 0})
    if not doc:
        return {"role": role, "layout": "grid", "theme": "dark", "components": []}
    return doc


@app.put("/api/v1/ui-config/{role}", status_code=204)
async def save_ui_config(role: str, schema: UISchema):
    db = get_db()
    await db["ui_schemas"].replace_one({"role": role}, schema.model_dump(), upsert=True)


# -- Alerts -------------------------------------------------------------------
@app.get("/api/v1/alerts")
async def get_alerts(limit: int = Query(50, le=200)):
    db     = get_db()
    cursor = db["alerts"].find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
    return await cursor.to_list(length=limit)


@app.patch("/api/v1/alerts/{alert_id}/acknowledge", status_code=200)
async def acknowledge_alert(alert_id: str):
    updated = await PredictiveHMI.instance().acknowledge_alert(alert_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"acknowledged": True, "alert_id": alert_id}


# -- Sensor snapshot + zone health --------------------------------------------
@app.get("/api/v1/sensors/status")
async def get_sensor_status():
    db = get_db()
    pipeline = [
        {"$sort": {"timestamp": -1}},
        {"$group": {"_id": "$sensor_id", "latest": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$latest"}},
        {"$project": {"_id": 0}},
    ]
    return await db["sensor_readings"].aggregate(pipeline).to_list(length=100)


@app.get("/api/v1/zones/health")
async def get_zones_health():
    return PredictiveHMI.instance().zone_health_summary()


# -- Health probe -------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "version": "4.0.0", "timestamp": datetime.now(timezone.utc).isoformat()}


# -- WebSocket ----------------------------------------------------------------
@app.websocket("/ws/{role}")
async def websocket_endpoint(ws: WebSocket, role: str):
    await manager.connect(ws, role)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws, role)
    except Exception:
        manager.disconnect(ws, role)
