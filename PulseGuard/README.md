# PulseGuard — Digital Twin Command Center

> **A real-time Industrial IoT dashboard that watches 12 factory sensors across 3 zones, predicts failures before they happen, and collapses noisy alerts into smart summaries — so operators stop drowning in alarms.**

---

## What is PulseGuard?

PulseGuard is a full-stack web application that simulates a factory floor and gives you a live "Digital Twin" view of everything happening inside it. Think of it like a control room from a sci-fi film — dark glassmorphism UI, live pulsing sensor nodes, and an AI that raises its hand *before* something breaks.

### The Problem it Solves — Alarm Fatigue
In real factories, hundreds of sensor alerts fire every hour. Operators stop paying attention because 90% are noise. PulseGuard's AI engine:
- **Detects anomalies** using statistics (flags a sensor that spikes beyond its normal range)
- **Predicts failures** 30 seconds before they happen using trend analysis
- **Collapses zone-wide events** into one smart alert instead of 10 individual ones

---

## How it Works — Simple Overview

```
[Simulator]  →  POST sensor readings every 2s
     ↓
[FastAPI Backend]  →  AI Engine analyses each reading
     ↓                  ↓ anomaly?  ↓ trending to fail?  ↓ zone-wide event?
[MongoDB]  stores all readings and alerts
     ↓
[WebSocket]  pushes live data to the browser instantly
     ↓
[React Dashboard]  shows Digital Twin grid, charts, alert feed
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Tailwind CSS, Framer Motion, Recharts |
| Backend | FastAPI (Python), WebSockets |
| AI Engine | NumPy — sliding window + linear regression |
| Database | MongoDB (via Motor async driver) |
| Simulator | Python multithreaded — 12 sensors, 3 zones |

---

## Project Structure

```
PulseGuard/
├── backend/
│   ├── app/
│   │   ├── main.py          ← FastAPI app — all REST + WebSocket endpoints
│   │   ├── ai_engine.py     ← PredictiveHMI: anomaly, prediction, zone alarm
│   │   ├── models.py        ← Pydantic data models
│   │   ├── database.py      ← MongoDB connection (Motor)
│   │   └── __init__.py
│   ├── simulator.py         ← Fake factory floor — posts data every 2s
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.jsx                        ← Root layout, WebSocket state
    │   ├── components/
    │   │   ├── DigitalTwinGrid.jsx        ← 3-zone pulsing factory map
    │   │   ├── AlertFeed.jsx              ← Live AI-enriched alert panel
    │   │   ├── ComponentRegistry.jsx      ← Maps type strings → components
    │   │   ├── DynamicGrid.jsx            ← Metadata-driven layout engine
    │   │   ├── RadialGauge.jsx            ← Animated SVG arc gauge
    │   │   ├── SensorChart.jsx            ← Line / Area / Bar charts
    │   │   ├── StatusCard.jsx             ← Single sensor card
    │   │   ├── CommandPalette.jsx         ← Ctrl+K quick-switch panel
    │   │   └── ZoneSummaryBar.jsx         ← Z1/Z2/Z3 health pills in header
    │   ├── hooks/
    │   │   ├── useIndustrialSocket.js     ← Auto-reconnect WebSocket hook
    │   │   └── useVoiceAlerts.js          ← Voice alerts (currently disabled)
    │   └── services/
    │       └── api.js                     ← Axios instance + WS factory
    └── package.json
```

---

## Prerequisites — What You Need Installed

| Tool | Version | Check if installed |
|---|---|---|
| Python | 3.10+ | `python --version` |
| Node.js | 18+ | `node --version` |
| MongoDB | Any | Running as a Windows service |
| npm | comes with Node | `npm --version` |

---

## How to Run (Windows — Step by Step)

You need **4 separate PowerShell windows**.

### Step 1 — Start MongoDB
MongoDB runs as a Windows service. Start it once (requires Admin):
```powershell
Start-Process powershell -Verb RunAs -ArgumentList "-Command Start-Service MongoDB"
```
> **One-time tip:** Open `services.msc`, find **MongoDB Server**, set Startup type to **Automatic** so it starts on boot.

---

### Step 2 — Install Python packages (first time only)
```powershell
python -m pip install -r "c:\Users\INNISAR4\source\repos\Pro\PulseGuard\backend\requirements.txt"
```

---

### Step 3 — Start the Backend API
```powershell
python -m uvicorn app.main:app --reload --port 8000 --app-dir "c:\Users\INNISAR4\source\repos\Pro\PulseGuard\backend"
```
Wait until you see: `Application startup complete.`

---

### Step 4 — Start the Frontend (new terminal)
```powershell
Set-Location "c:\Users\INNISAR4\source\repos\Pro\PulseGuard\frontend"
npm install        # first time only
npm run dev
```
Wait until you see: `VITE ready at http://localhost:3000/`

---

### Step 5 — Start the Simulator (new terminal)
```powershell
python "c:\Users\INNISAR4\source\repos\Pro\PulseGuard\backend\simulator.py"
```
You will see 12 sensors printing live readings every 2 seconds.

---

## Open the Dashboard

| URL | What's there |
|---|---|
| http://localhost:3000 | **PulseGuard HMI** — the full dashboard |
| http://localhost:8000/health | Backend health check — should return `{"status":"ok"}` |
| http://localhost:8000/docs | FastAPI Swagger UI — test all API endpoints |

---

## Dashboard Features

| Feature | How to use it |
|---|---|
| **Digital Twin** | Top panel — 3 zones, each sensor pulses green/amber/red live |
| **Zone Health Bar** | Header pills show Z1/Z2/Z3 status at a glance |
| **Intelligence Feed** | Right panel — AI alerts with criticality score bar |
| **Role Switch** | Top-right buttons — Operator / Engineer / Admin show different layouts |
| **Command Palette** | Press `Ctrl+K` — instantly switch role from keyboard |
| **Dismiss Alert** | Click "Dismiss" on any alert — persisted to database |
| **Critical Mode** | When a CRITICAL alert fires, the entire screen border pulses red |

---

## AI Alert Types

| Alert Type | What it means | Colour |
|---|---|---|
| `CRITICAL` | Sensor spiked beyond its 2σ normal range right now | Red |
| `PREDICTION` | Sensor is trending toward failure — breach in <30s | Violet |
| `ZONE_ALARM` | 3+ sensors in the same zone failed at once | Rose/Pink |
| `WARNING` | Elevated reading, not yet critical | Amber |
| `INFO` | Normal operational event | Blue |

---

## API Reference (Key Endpoints)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/telemetry` | Submit a sensor reading (simulator uses this) |
| `GET` | `/api/v1/alerts` | Fetch recent alert history |
| `PATCH` | `/api/v1/alerts/{id}/acknowledge` | Mark an alert as acknowledged |
| `GET` | `/api/v1/sensors/status` | Latest value for every sensor |
| `GET` | `/api/v1/zones/health` | Live health (`ok`/`warning`/`critical`) per zone |
| `GET` | `/api/v1/ui-config?role=` | Layout schema for a role |
| `PUT` | `/api/v1/ui-config/{role}` | Save a modified layout |
| `WS` | `/ws/{role}` | WebSocket — real-time push for operator/engineer/admin |

---

## Troubleshooting

**"Cannot open MongoDB service"**
→ Run the Start-Service command as Administrator (see Step 1 above)

**"can't open file simulator.py"**
→ Always use the full path: `python "c:\Users\...\backend\simulator.py"`

**"ModuleNotFoundError: No module named 'app'"**
→ Use `--app-dir` flag as shown in Step 3, not `cd backend && uvicorn`

**Frontend shows "Disconnected" badge**
→ Make sure the backend is running first, then refresh the browser

**No data in Digital Twin grid**
→ Make sure the simulator (Step 5) is running — it's what generates sensor data

---

## GitHub

Repository: https://github.com/NiranjanSaravanakumar/PluseGuard


## Architecture

```
simulator.py  ──POST /api/v1/telemetry──>  FastAPI (app/main.py)
                                                   |
                                           app/engine.py  (sliding-window AI)
                                                   |
                                           MongoDB  (Motor async driver)
                                                   |
                                        WebSocket broadcast
                                                   |
                                         React HMI  (DynamicGrid)
```

## Cold Start Guide

### Step 1 — Start MongoDB

**With Docker:**
```bash
docker run -d --name pulseguard-mongo -p 27017:27017 mongo:7
```
**Or** use your local MongoDB installation.

---

### Step 2 — Start the Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy env template and configure
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux

# Start the API server
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/docs`

---

### Step 3 — Start the Frontend

```bash
cd frontend

npm install
npm run dev
```

Open `http://localhost:3000` in your browser.

---

### Step 4 — Start the Simulator

Open a new terminal:

```bash
cd backend
python simulator.py
```

The simulator will start POSTing sensor readings every 2 s. A **critical anomaly spike** is injected every 60 s.

---

### Docker (all-in-one)

```bash
docker-compose up --build
```

---

## API Reference

| Method | Endpoint                  | Description                          |
|--------|---------------------------|--------------------------------------|
| POST   | `/api/v1/telemetry`       | Ingest a sensor reading              |
| GET    | `/api/v1/ui-config?role=` | Fetch metadata-driven UI schema      |
| GET    | `/api/v1/alerts?limit=`   | Fetch recent alert history           |
| GET    | `/health`                 | Liveness probe                       |
| WS     | `/ws/{role}`              | Real-time data stream                |

## AI Engine

- **Sliding Window Anomaly Detection**: If the current value is > 2 standard deviations from the last 10 stored readings, a `CRITICAL` alert is generated and persisted.
- **Criticality Score** (0–100): `(deviation × 10 × 0.4) + (sensor_priority × 0.3) + (rate_of_change × 0.3)`

## Roles

| Role       | View                                          |
|------------|-----------------------------------------------|
| `operator` | Alert feed + 2 status cards + 2 charts        |
| `engineer` | Alert feed + 4 radial gauges + 4 charts       |

UI schemas are stored in MongoDB and served dynamically via `/api/v1/ui-config`.
