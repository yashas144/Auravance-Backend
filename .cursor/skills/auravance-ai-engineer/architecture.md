# Auravance architecture reference

Read this when changing APIs, storage, ingest, or deploy. Keep
`docs/backend-architecture.md` (target) and `docs/demo-backend-architecture.md`
(what shipped for demo) in sync with code.

## Runtime topology (today)

```
simulate_telemetry.py / replay_telemetry.py
        │  POST /api/v1/telemetry/ingest[/batch]
        ▼
   FastAPI (app/main.py)
        │
        ├─ SQLite  data/auravance_demo.db
        ├─ score_asset() → Isolation Forest + HGB (+ rules fallback)
        ├─ alerts (cooldown)
        └─ rag_service.root_cause() → knowledge chunks + OpenAI or playbook
                ▲
        auravance-frontend (React App.jsx, Vite proxy /api → :8000)
```

Target topology (not yet built): sensors → MQTT broker → ingestion service →
stream features → TimescaleDB → XGBoost/LSTM/Isolation Forest → alerts → RAG
over pgvector. See `docs/backend-architecture.md`.

## Telemetry contract

Ingest payload:

```json
{
  "timestamp": "2026-05-15T14:22:31Z",
  "asset_id": "compressor-17",
  "metrics": {
    "temperature_c": 84.2,
    "vibration_rms": 0.63,
    "pressure_bar": 5.2,
    "current_a": 11.7
  },
  "source": "api",
  "source_context": {}
}
```

Replay fills `source_context` with original timestamp, raw values, ground-truth
status (`NORMAL`, `BROKEN`, `RECOVERING`, `AIR_LEAK`, `FAILED`), units, and
`dataset` (`kaggle-pump-sensor`, `metropt-3`, `ims-bearings`). The dashboard
shows ground truth next to model output. Do not drop `source_context`.

Batch: `{"readings":[...]}` with `min_length=1`, `max_length=500`. Unknown
asset IDs fail the whole batch (404).

## Prediction contract

`GET /api/v1/predictions/assets/{asset_id}/latest` returns:

- `anomaly_score` 0–1, `anomaly_label` (`normal` | `warning` | `high-risk`)
- `failure_probability_72h` 0–1
- `estimated_rul_hours` > 0
- `dominant_signal` (temperature | vibration | pressure | current | bearing_pattern | pressure_instability)
- `anomaly_model_version`, `failure_model_version`, `rul_model_version`

Scoring uses the last 12 history points (`PredictionService.get_latest`).
Ingest alerting uses the last 8.

## Equipment profiles

| Asset type | Profile | Dataset | Failure character |
|---|---|---|---|
| pump, cooling-system | pump | Kaggle pump-sensor, 1-min, 7 breakdowns | mixed; 72h forecast weak |
| compressor | compressor | MetroPT-3, 5-min, 4 air leaks | sudden; use `SuddenFailureClassifier` |
| motor, drive, conveyor | motor | NASA/IMS, 10-min vibration RMS, 3 bearing failures | gradual degradation |

Default profile is `pump`. Profile artifact paths are in
`app/services/model_profiles.py`.

## REST surface (`settings.api_prefix` = `/api/v1`)

| Area | Routes |
|---|---|
| Health | `GET /health` |
| Auth | `POST /auth/login` |
| Assets | `/assets` |
| Master data | `/plants`, `/vendors`, `/equipment`, `/sensors`, `/users`, `/maintenance-schedules`, `/work-orders`, `/defects` |
| Telemetry | `POST /telemetry/ingest`, `POST /telemetry/ingest/batch`, `GET /telemetry/ingest/targets`, latest/history |
| Predictions | latest + `GET /predictions/models/status` |
| Diagnostics | `GET /diagnostics/status`, `POST /diagnostics/root-cause`, `GET /diagnostics/retrieve` |
| Knowledge | `/knowledge/documents`, `/knowledge/search` |
| Alerts | `GET /alerts` |
| Datasets | `GET /datasets` |

User JWT: `Authorization: Bearer`. Ingest: `X-Ingest-Key` when
`AURAVANCE_INGEST_API_KEY` is set.

## Storage

SQLite at `AURAVANCE_DEMO_DB_PATH` (default `data/auravance_demo.db`).
`init_db()` seeds demo plants, assets, vendors, equipment, users. Do not treat
the committed DB as a schema migration tool — change `app/core/db.py` DDL and
seed data together.

## Config (`app/core/config.py`)

Loaded from `.env` without overriding existing process env. Important
keys: `OPENAI_API_KEY`, `AURAVANCE_INGEST_API_KEY`, `AURAVANCE_AUTH_SECRET_KEY`,
`AURAVANCE_RAG_*`, model paths, data/knowledge roots, alert cooldown.

## Frontend

- Sibling repo `auravance-frontend`: single file `src/App.jsx` plus `styles.css`.
- Nav groups: Operations (Monitoring, Root Cause Analysis), Master Data, Execution, Admin.
- `VITE_API_BASE_URL` optional; local default `/api/v1` through the Vite proxy.
- Session: `localStorage` key `auravance.currentUser`.

## Deploy

Terraform under `terraform/`: Cloud Run backend, Firebase Hosting frontend,
Secret Manager, Artifact Registry. Follow `terraform/README-DEPLOY.md`. Free-tier
demo, not the MQTT/Timescale production design.

## Target MQTT (when implementing)

Topic: `plants/{plant_id}/lines/{line_id}/assets/{asset_id}/telemetry`

Subscriber responsibilities: validate, normalize timestamps/units/keys, persist
raw telemetry, call `telemetry_service.ingest` / `ingest_batch`. Keep REST ingest
for the simulator and replay.
