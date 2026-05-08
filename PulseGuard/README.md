# PulseGuard — Industrial Intelligence Platform

A production-ready IIoT HMI that solves **Alarm Fatigue** through AI-driven anomaly detection, sliding-window statistical analysis, and a metadata-driven dynamic UI.

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
