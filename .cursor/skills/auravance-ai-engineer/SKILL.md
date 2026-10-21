---
name: auravance-ai-engineer
description: >-
  Guides work on the Auravance backend: FastAPI telemetry ingest, Isolation
  Forest / Gradient Boosting failure and RUL models, MQTT/IoT pipelines, ETL,
  and RAG diagnostics. Use when editing this backend, ML training, MQTT
  ingestion, RAG, telemetry, predictions, alerts, equipment profiles, or
  closing the gap to production MQTT, XGBoost, and LSTM. The React dashboard
  is the sibling repo auravance-frontend.
---

# Auravance AI Engineer

Act as the platform AI engineer for this backend repo. Ship working software
that matches the product north star **without overstating what the code does**.

The React dashboard is a **separate repository**: `auravance-frontend`. Do not
re-create frontend sources here. Keep the telemetry, prediction, and RAG HTTP
contracts stable so that repo can keep calling `/api/v1`.

## Product north star

Use this wording verbatim when describing the product. Do not paraphrase it in
READMEs, PRs, or comments unless the user asks:

- Built a full-stack AI platform (React, FastAPI) for real-time equipment monitoring and failure prediction using XGBoost and LSTM, improving detection accuracy by 30%.
- Engineered scalable event-driven IoT ingestion pipelines using MQTT and Python for high-frequency sensor telemetry with low latency and high reliability.
- Designed scalable ETL and event-driven MQTT pipelines processing 1M+ sensor records/day, enabling predictive maintenance, anomaly detection, and RUL insights with sub-minute latency.
- Built a RAG-based root cause analysis system over equipment manuals to generate explainable diagnostics and maintenance recommendations.

Those bullets are the **target capability**. Treat them as the build goal, not as
a description of the current tree unless the matching code exists.

## Current vs target

| Capability | In this repo today | Target |
|---|---|---|
| Full-stack monitoring | FastAPI `/api/v1`; dashboard is `auravance-frontend` | Same, production-hardened |
| Failure / RUL models | sklearn `HistGradientBoosting*` per equipment profile; Isolation Forest anomalies; rules fallback | XGBoost tabular scoring + LSTM sequence models |
| MQTT IoT ingest | Not implemented. REST `POST /telemetry/ingest` and `/ingest/batch` | MQTT broker + Python subscriber, topic `plants/{plant_id}/lines/{line_id}/assets/{asset_id}/telemetry` |
| ETL / high volume | Offline scripts over Kaggle pump, MetroPT-3, NASA/IMS; SQLite demo DB | Event-driven pipeline, 1M+ records/day, sub-minute latency, TimescaleDB |
| RAG diagnostics | OpenAI embeddings + TF-IDF retrieval over manuals/guides; local playbook fallback | Same contract, stronger index (pgvector) |
| Accuracy claims | Honest leave-one-failure-out metrics in model JSON; no coded "30%" baseline | Publish a measured baseline-vs-model delta before claiming 30% |

Never write code comments or API docs that imply MQTT, XGBoost, or LSTM are
live until they are.

## First actions on every task

1. Identify the layer: ingest, storage, ML, RAG, API, deploy.
2. Read the existing module before adding a new one. Prefer extending
   `app/services/*` over creating parallel stacks.
3. Keep the **telemetry contract**, **prediction contract**, and **RAG contract**
   stable (see [architecture.md](architecture.md)).
4. If the change is ML, follow [ml-playbook.md](ml-playbook.md). If RAG, follow
   [rag-playbook.md](rag-playbook.md).
5. After code changes, run the relevant tests.

## Repo map

```
app/api/routes/       REST surface
app/core/             settings, SQLite, auth/ingest key
app/models/schemas.py Pydantic contracts
app/services/         scoring, anomaly, prognostics, RAG, telemetry, alerts
app/ingestion/        replay helpers used by live streamer
scripts/              ETL, knowledge index, training, simulator, replay
artifacts/models/     joblib + sidecar JSON metadata
knowledge/            markdown guides + processed PDF chunks
docs/                 target architecture vs demo architecture
terraform/            Cloud Run + Firebase Hosting site resource
```

Python `>=3.11`. Deps live in `pyproject.toml`. Dashboard: sibling
`auravance-frontend` (React 18 + Vite).

## Non-negotiable conventions

- **Four sensor channels** on the wire: `temperature_c`, `vibration_rms`,
  `pressure_bar`, `current_a`. Do not expand the public schema unless the
  dashboard repo and all three model profiles are updated together.
- **Equipment profiles**: `pump` (Kaggle), `compressor` (MetroPT-3), `motor`
  (IMS). Asset types `cooling-system` → pump; `drive`/`conveyor` → motor.
- **API stays up if models fail to load.** `score_asset` falls back to the
  rules scorer and reports `fallback_active`.
- **Honest serving for replay.** Replayed readings with
  `source_context.dataset` matching the training set use the stored
  leave-one-failure-out fold estimator (`+heldout-N`).
- **Do not leak secrets.** Keys come from env / `.env`. Never commit `.env` or
  `terraform.tfvars`.
- **Ingest auth ≠ user auth.** `X-Ingest-Key` guards ingest. JWT Bearer guards
  dashboard reads/writes.
- **Alerts are scored on ingest** from the last 8 points, with cooldown
  (`AURAVANCE_ALERT_COOLDOWN_SECONDS`, default 300) unless severity changes.
- **Typed schemas first.** Change `app/models/schemas.py`, then services,
  routes, then tests. Tell the user if `auravance-frontend` callers need a
  matching change.
- **SQLite is the demo store.** Production direction is PostgreSQL +
  TimescaleDB + pgvector (`docs/backend-architecture.md`).

## Implementation workflow

```
Task:
- [ ] Layer identified; existing module read
- [ ] Contract unchanged or updated in lockstep with the frontend repo
- [ ] Fallback path still works if model/broker/OpenAI is down
- [ ] Tests or replay/simulator path updated
- [ ] Docs match the code (no false MQTT/XGBoost/LSTM claims)
```

MQTT, when added, must emit the same ingest contract (subscribe → normalize →
`telemetry_service`). Do not bypass scoring.

## Tests and local run

```bash
pip install -e . && pytest tests/
uvicorn app.main:app --reload
```

## Upgrade order (when asked to close north-star gaps)

1. Keep REST ingest working; add MQTT as an additional producer into the same service.
2. Swap or add XGBoost behind the existing artifact schema (`artifact_schema_version: 1`).
3. Add LSTM only after windowed sequence features exist; serve it beside tabular models.
4. Move telemetry to TimescaleDB once MQTT volume needs it.
5. Measure detection accuracy against the current baseline **before** claiming a 30% improvement.

## Additional resources

- Module map, payloads, and API list: [architecture.md](architecture.md)
- Training, evaluation, serving rules: [ml-playbook.md](ml-playbook.md)
- Knowledge index and diagnostics: [rag-playbook.md](rag-playbook.md)
