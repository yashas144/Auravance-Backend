"""Generate docs/Auravance-Big-Picture.docx — architecture, models, RAG, sensors, demo."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


BACKEND_DIR = Path(__file__).resolve().parents[1]
OUTPUT = BACKEND_DIR / "docs" / "Auravance-Big-Picture.docx"
FIGURES = BACKEND_DIR / "docs" / "architecture-diagrams"

NAVY = RGBColor(0x0B, 0x2E, 0x4A)
TEAL = RGBColor(0x0D, 0x6E, 0x7A)
MUTED = RGBColor(0x44, 0x55, 0x66)


def set_run(run, *, bold=False, size=11, color=None, italic=False):
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(size)
    run.font.name = "Calibri"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    if color is not None:
        run.font.color.rgb = color


def add_heading(doc, text, level=1):
    p = doc.add_heading(text, level=level)
    for run in p.runs:
        run.font.color.rgb = NAVY if level == 1 else TEAL
        run.font.name = "Calibri"
    return p


def add_para(doc, text, *, bold=False, italic=False, size=11, space_after=8):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(0)
    run = p.add_run(text)
    set_run(run, bold=bold, italic=italic, size=size, color=MUTED if italic and not bold else None)
    return p


def add_bullets(doc, items):
    for item in items:
        p = doc.add_paragraph(item, style="List Bullet")
        p.paragraph_format.space_after = Pt(3)
        for run in p.runs:
            run.font.name = "Calibri"
            run.font.size = Pt(11)


def add_figure(doc, filename: str, caption: str) -> None:
    path = FIGURES / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing diagram {path}. Run scripts/generate_architecture_diagrams.py first.")
    picture = doc.add_paragraph()
    picture.alignment = WD_ALIGN_PARAGRAPH.CENTER
    picture.paragraph_format.space_before = Pt(8)
    picture.paragraph_format.space_after = Pt(2)
    run = picture.add_run()
    run.add_picture(str(path), width=Inches(6.5))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(12)
    r = cap.add_run(caption)
    set_run(r, italic=True, size=10, color=MUTED)


def add_table(doc, headers, rows):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    for i, header in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = header
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                set_run(run, bold=True, size=10, color=NAVY)
    for r_index, row in enumerate(rows, start=1):
        for c_index, value in enumerate(row):
            cell = table.rows[r_index].cells[c_index]
            cell.text = str(value)
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    set_run(run, size=10)
    doc.add_paragraph()
    return table


def build() -> Path:
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.85)
    section.bottom_margin = Inches(0.85)
    section.left_margin = Inches(0.95)
    section.right_margin = Inches(0.95)

    title = doc.add_paragraph()
    run = title.add_run("Auravance")
    set_run(run, bold=True, size=26, color=NAVY)
    subtitle = doc.add_paragraph()
    run = subtitle.add_run("Big picture: architecture, models, RAG, and sensors")
    set_run(run, bold=True, size=16, color=TEAL)
    add_para(
        doc,
        "Written from the running code in auravance-backend and auravance-frontend. Date: 24 October 2026.",
        italic=True,
    )

    add_heading(doc, "1. How to read this", 1)
    add_para(
        doc,
        "This is the single map of the product: what it is, why each major piece exists, "
        "how it was implemented, how machine-learning and root-cause (RAG) work, how a real "
        "plant would attach sensors, and how the demo pretends those sensors exist. It is an "
        "engineering brief. It is not a resume.",
    )
    add_para(
        doc,
        "The product north star — the build goal, not a claim that every line below is already "
        "a plant-scale system — is:",
        italic=True,
    )
    add_bullets(
        doc,
        [
            "Built a full-stack AI platform (React, FastAPI) for real-time equipment monitoring and failure prediction using XGBoost and LSTM, improving detection accuracy by 30%.",
            "Engineered scalable event-driven IoT ingestion pipelines using MQTT and Python for high-frequency sensor telemetry with low latency and high reliability.",
            "Designed scalable ETL and event-driven MQTT pipelines processing 1M+ sensor records/day, enabling predictive maintenance, anomaly detection, and RUL insights with sub-minute latency.",
            "Built a RAG-based root cause analysis system over equipment manuals to generate explainable diagnostics and maintenance recommendations.",
        ],
    )
    add_para(
        doc,
        "Sections 4–9 describe what the repositories actually do. Section 10 is how live sensors "
        "would plug into that contract. Section 11 is the demo substitute. Do not quote a "
        "product-wide 30% accuracy improvement; the measured replay delta is mixed by equipment type.",
    )

    add_heading(doc, "2. What Auravance is", 1)
    add_para(
        doc,
        "Auravance watches industrial equipment and turns four sensor channels into three decisions: "
        "does this look abnormal, is a failure likely within 72 hours, and about how many hours of "
        "useful life remain. A technician can then ask why, and get causes and actions grounded in "
        "equipment manuals. The operator surface is a React console. The engine is a FastAPI service. "
        "They talk only over HTTP at /api/v1.",
    )
    add_para(
        doc,
        "The business reason is unplanned downtime. Pumps, compressors, and motors already emit "
        "temperature, vibration, pressure, and current. Calendar maintenance either services healthy "
        "machines too early or still misses a sudden leak. Auravance is the decision layer between "
        "those readings and a maintenance action.",
    )
    add_figure(
        doc,
        "fig-01-system-context.png",
        "Figure 1. Two repositories. The dashboard never loads models. The API never serves React.",
    )

    add_heading(doc, "3. Why the architecture looks like this", 1)
    add_para(
        doc,
        "The design keeps one ingest contract and lets producers change. A simulator, a replay of a "
        "public dataset, a local MQTT broker, or a future plant gateway all end in the same function: "
        "telemetry_service.ingest. Scoring, storage, and the dashboard do not care which door the "
        "reading used. That is why MQTT was added beside REST instead of as a second stack.",
    )
    add_table(
        doc,
        ["Choice", "Why", "What it is not"],
        [
            ["FastAPI", "Python is where the models live; Pydantic keeps the HTTP contract typed", "A separate inference microservice"],
            ["React + Vite", "Operator console in a sibling repo so UI and models can ship separately", "Embedded in the API image"],
            ["Four channels only", "Dashboard, database columns, and all three model profiles stay in lockstep", "A free-form tag historian"],
            ["REST ingest", "Simple, testable, and what replay uses by default", "How a PLC prefers to talk"],
            ["MQTT", "The protocol gateways and sensors already use; publish/subscribe, many assets", "An HA cluster (EMQX/HiveMQ)"],
            ["PostgreSQL", "Shared store for plants, users, work orders, and telemetry when more than one process writes", "Required for pytest"],
            ["TimescaleDB", "Telemetry is append-only time series; a hypertable chunks by time", "InfluxDB; retention and rollups are not on"],
            ["SQLite", "Laptop and tests with no Docker", "The Path B store"],
            ["Redis + worker", "Ingest should persist quickly; models run off the API process", "Required; unset Redis scores inline"],
            ["Rules fallback", "The API must stay up if a model file fails to load", "The production model"],
            ["RAG on request", "Language-model calls are slow and costly; they must not sit on every sensor tick", "Automatic diagnosis inside ingest"],
        ],
    )
    add_figure(
        doc,
        "fig-09-current-vs-target.png",
        "Figure 2. Solid boxes are in these repos. Dashed boxes are the production target.",
    )

    add_heading(doc, "4. How a reading becomes a screen", 1)
    add_para(
        doc,
        "On a laptop with Docker (Path B): Mosquitto or REST delivers a reading, FastAPI validates "
        "the asset and the four metrics, Timescale stores the row, Redis receives the asset id, and "
        "the scoring worker loads the last eight points, runs the models, and may open an alert. "
        "The React app, after login, polls the last 24 history points and the latest prediction "
        "(scored on the last 12 points). Root-cause analysis is a button, not part of that hot path.",
    )
    add_para(
        doc,
        "Without Docker (Path A): the same HTTP API writes SQLite, MQTT is an in-process broker, "
        "and scoring runs inside uvicorn. GET /api/v1/health says which mode you are in: storage "
        "is sqlite or postgresql; scoring is inline or worker.",
    )
    add_figure(
        doc,
        "fig-02-local-runtime.png",
        "Figure 3. Processes on a laptop. Compose replaces the embedded broker, SQLite, and inline scoring when the env vars are set.",
    )
    add_figure(
        doc,
        "fig-04-ingestion.png",
        "Figure 4. Every producer ends in telemetry_service. Predictions for the dashboard are a later GET.",
    )
    add_figure(
        doc,
        "fig-10-request-path.png",
        "Figure 5. The console never calls ingest. Machines use X-Ingest-Key; people use a JWT.",
    )

    add_heading(doc, "5. How the features were implemented", 1)
    add_heading(doc, "5.1 Ingest", 2)
    add_para(
        doc,
        "REST is POST /api/v1/telemetry/ingest and /ingest/batch (1–500 readings). An unknown asset "
        "id fails the whole batch with 404. MQTT is a subscriber started in the API lifespan "
        "(app/ingestion/mqtt.py). It connects to Mosquitto when AURAVANCE_MQTT_EMBEDDED=false, "
        "otherwise it starts a small in-process MQTT 3.1.1 broker so tests need no Docker. Each "
        "message is decoded in mqtt_protocol.py into the same TelemetryIngestRequest REST uses. "
        "The asset id in the topic wins over the JSON body.",
    )
    add_para(
        doc,
        "Topic: plants/{plant_id}/lines/{line_id}/assets/{asset_id}/telemetry",
        italic=True,
    )
    add_para(
        doc,
        '{ "timestamp": "2026-05-15T14:22:31Z", "asset_id": "compressor-17", '
        '"metrics": { "temperature_c": 84.2, "vibration_rms": 0.63, "pressure_bar": 5.2, "current_a": 11.7 }, '
        '"source": "mqtt", "source_context": {} }',
        italic=True,
    )
    add_para(
        doc,
        "source_context is preserved. Replay puts the original timestamp, raw values, dataset name, "
        "and ground-truth status there (NORMAL, BROKEN, RECOVERING, AIR_LEAK, FAILED). The dashboard "
        "shows that next to the model. Do not drop it.",
    )

    add_heading(doc, "5.2 Storage", 2)
    add_para(
        doc,
        "One database holds both relational master data and the time series. PostgreSQL is the "
        "system of record for plants, assets, equipment, sensors, users, alerts, schedules, work "
        "orders, defects, and the knowledge index. TimescaleDB is an extension on that same "
        "Postgres, not a second product. On startup, init_db() creates telemetry and then "
        "create_hypertable('telemetry', 'timestamp') so rows are chunked by time. The compose "
        "image is timescale/timescaledb:2.17.2-pg16, published on host port 5433 because a local "
        "Windows Postgres often already owns 5432.",
    )
    add_para(
        doc,
        "If AURAVANCE_DATABASE_URL is empty, the same schema is SQLite at data/auravance_demo.db "
        "(WAL mode). Pytest uses that path. Retention policies, compression, and continuous "
        "aggregates are not configured. pgvector is not the RAG index.",
    )
    add_figure(
        doc,
        "fig-07-sqlite.png",
        "Figure 6. Table groups. On Path B these tables live in Postgres; telemetry is the Timescale hypertable. Dashed boxes are still targets.",
    )

    add_heading(doc, "5.3 Scoring off the API process", 2)
    add_para(
        doc,
        "Ingest used to score inside the request. That couples model latency to every sensor write. "
        "Now telemetry_service stores the rows and calls schedule_ingest_scoring. If "
        "AURAVANCE_REDIS_URL is set, the asset id is pushed to the Redis list auravance:score and "
        "python -m app.workers.scoring_worker runs score_asset on the last eight points and applies "
        "the alert cooldown (default 300 seconds unless severity rises). If Redis is missing or "
        "down, scoring stays inline so a laptop and the tests still raise alerts. The dashboard "
        "prediction (last 12 points) is still computed on GET /predictions/latest.",
    )

    add_heading(doc, "5.4 Auth and the console", 2)
    add_para(
        doc,
        "People: POST /auth/login returns a JWT; the React app stores it and sends Authorization: "
        "Bearer. Machines: X-Ingest-Key when AURAVANCE_INGEST_API_KEY is set. A dashboard token "
        "cannot ingest, and the ingest key cannot open the console. The UI is module state in "
        "App.jsx (no client router): Monitoring, Root Cause Analysis, master data, work orders, "
        "and admin users. Local Vite proxies /api to port 8000.",
    )
    add_figure(
        doc,
        "fig-03-frontend-modules.png",
        "Figure 7. Console modules. Four cards only: temperature, vibration, pressure, current.",
    )

    add_heading(doc, "6. Machine-learning models", 1)
    add_para(
        doc,
        "Three questions stay separate. Mixing them is how a demo lies about remaining life.",
    )
    add_bullets(
        doc,
        [
            "Anomaly — does this look unlike healthy operation? Isolation Forest trained on healthy rows. If the file fails to load, a rules mix of normalized channels plus trend.",
            "Failure — probability of failing now or within 72 hours. LSTM sequence (window of 12) when PyTorch and the sequence artifact are present; else XGBoost if that artifact exists; else HistGradientBoosting; else rules.",
            "RUL — estimated hours until the next failure, capped. XGBoost if present, else HistGradientBoosting, else a value derived from the failure probability. A classification score is not reused as RUL except the documented compressor sudden-failure wrappers.",
        ],
    )
    add_para(
        doc,
        "The asset type selects a profile in app/services/model_profiles.py. Pump and cooling-system "
        "use the pump profile (Kaggle pump-sensor). Compressor uses MetroPT-3 air-compressor leaks. "
        "Motor, drive, and conveyor use NASA/IMS bearing run-to-failure. Features are the same four "
        "channels, centered and scaled with the transform stored in the artifact so live values match "
        "training. Pump source channels are anonymized, so their physical units are unknown and the "
        "anomaly model’s saved transform rescales them.",
    )
    add_para(
        doc,
        "Artifacts are joblib dicts with artifact_schema_version 1, plus a sibling JSON with the "
        "estimator stripped. GET /predictions/models/status reads that metadata, including "
        "fallback_active. Training is offline (scripts/train_anomaly_model.py, train_failure_model.py, "
        "train_rul_model.py, train_profile_models.py, train_xgboost_models.py, train_sequence_models.py). "
        "Evaluation is leave-one-failure-out: each failure cycle is scored by a model that did not "
        "train on it. When replay sends source_context.dataset matching that training set and the "
        "original timestamp falls in a held-out window, serving uses the stored +heldout-N estimator "
        "instead of the model that already saw the failure.",
    )
    add_figure(
        doc,
        "fig-05-scoring.png",
        "Figure 8. Serving order inside score_asset. Rules are the safety net, not the headline model.",
    )
    add_para(
        doc,
        "Honest limits, from training metadata and scripts/evaluate_detection_delta.py (ROC-AUC of "
        "ranking currently-failed replay rows above healthy rows, versus the rules scorer): pump "
        "failure leave-one-out AUC is about 0.66; compressor leak-in-progress is strong and a 72-hour "
        "forecast is not, because leaks are sudden; motor snapshots after downsampling are too sparse "
        "for a 30% claim, and the tabular motor score on that clip does not beat rules. Pump’s large "
        "gap versus rules is mostly a weak rules baseline on anonymized channels. Do not state a "
        "product-wide 30% detection improvement.",
        italic=True,
    )

    add_heading(doc, "7. RAG pipeline", 1)
    add_para(
        doc,
        "RAG here means: retrieve passages from equipment manuals and site guides, then write likely "
        "causes and actions that are allowed to use only those passages plus the latest score. It "
        "runs when someone posts to /diagnostics/root-cause. It does not run on MQTT or REST ingest.",
    )
    add_heading(doc, "7.1 Why", 2)
    add_para(
        doc,
        "A probability without a next action sends the technician back to a PDF folder. The model "
        "says which signal dominates (temperature, vibration, pressure, current, or a profile-specific "
        "pattern). Retrieval uses that signal plus the symptom text so the answer is about this asset, "
        "not a generic essay. If OpenAI is down, a local playbook still returns causes and actions.",
    )
    add_heading(doc, "7.2 How it was implemented", 2)
    add_para(
        doc,
        "Indexing is python scripts/prepare_knowledge.py. Sources are PDFs under knowledge/raw and "
        "markdown guides under knowledge/. The script extracts text, writes normalized files, chunks "
        "about 1200 characters with 200 overlap, builds TF-IDF-style vectors, and, when "
        "OPENAI_API_KEY is set, stores text-embedding-3-small vectors (1536 dimensions) in the "
        "database. Those vectors are JSON in the knowledge tables. They are not pgvector.",
    )
    add_para(
        doc,
        "At query time app/services/rag.py loads the latest prediction (404 if the asset has no "
        "telemetry), maps dominant_signal onto ISSUE_PLAYBOOK, retrieves about five chunks "
        "(OpenAI query embedding if the key works, otherwise TF-IDF), then calls the OpenAI "
        "Responses API (default gpt-4.1-mini, temperature 0.2) with a JSON schema. Instructions "
        "forbid inventing manuals or steps that are not in the evidence. On a missing key or an API "
        "error, the fallback extracts cause and action sentences from the chunks and the playbook. "
        "The response includes grounded_summary, likely_causes, recommended_actions, confidence, "
        "generation_mode, and evidence_snippets. Status reports openai_api_key_loaded as a boolean "
        "only.",
    )
    add_figure(
        doc,
        "fig-06-rag.png",
        "Figure 9. Diagnostics are request-driven. Both retrieval and generation have a local fallback.",
    )

    add_heading(doc, "8. How live sensors would connect", 1)
    add_para(
        doc,
        "The application does not speak to a sensor chip. A sensor or PLC speaks a plant protocol "
        "(Modbus, OPC-UA, a vendor gateway, sometimes Sparkplug). An edge gateway translates that "
        "into the Auravance payload and publishes it. The API already accepts that payload. What a "
        "plant still has to build is the gateway and a real broker in the plant network — not a new "
        "scoring API.",
    )
    add_figure(
        doc,
        "fig-11-enterprise-sensors.png",
        "Figure 10. Enterprise path. The subscriber, hypertable, worker, and dashboard exist. The gateway and an HA broker are the plant’s job.",
    )
    add_heading(doc, "8.1 Steps on a real line", 2)
    add_bullets(
        doc,
        [
            "Register the asset first (asset id, type, plant id, line id) through the API or the equipment master. Ingest rejects unknown ids.",
            "Pick the profile by asset type: pump, compressor, or motor. A drive or conveyor is scored as a motor; a cooling skid as a pump. The gateway does not choose the model.",
            "On the gateway, map native tags onto temperature_c, vibration_rms, pressure_bar, and current_a. If a machine lacks one channel, send null for that field; do not invent a fifth public metric without changing the dashboard and all three profiles together.",
            "Publish JSON to plants/{plant_id}/lines/{line_id}/assets/{asset_id}/telemetry on the MQTT broker. Point the API at that broker with AURAVANCE_MQTT_EMBEDDED=false and AURAVANCE_MQTT_BROKER_HOST/PORT. Set AURAVANCE_DATABASE_URL to Postgres/Timescale and AURAVANCE_REDIS_URL so scoring runs in the worker.",
            "Give the gateway credentials that match the ingest key (MQTT username/password, or X-Ingest-Key if the gateway uses REST instead).",
            "The subscriber decodes the message, writes telemetry, and enqueues scoring. Alerts use the last eight points. Operators watch Monitoring over JWT. They press Root Cause Analysis when they want a manual-backed explanation.",
            "If the site cannot run MQTT, the same JSON can be POSTed to /api/v1/telemetry/ingest or /ingest/batch. That is a supported door, not a second data model.",
        ],
    )
    add_heading(doc, "8.2 What this repo does not include", 2)
    add_para(
        doc,
        "There is no OPC-UA client, no Sparkplug B decoder, no Kepware/Ignition/PI adapter, and no "
        "per-device certificate store. Mosquitto in docker-compose is one broker for a laptop, not "
        "a multi-node HA cluster. Device identity at enterprise level would be mTLS or per-gateway "
        "credentials on that external broker; the subscriber contract (topic + four channels + "
        "telemetry_service) would stay the same.",
    )

    add_heading(doc, "9. How the demo simulates that plant", 1)
    add_para(
        doc,
        "There are no PLCs in this repository. The demo replays public recordings as if the machines "
        "were live, and it pushes them through the same ingest function a gateway would use. That is "
        "why the dashboard can show a compressor in AIR_LEAK beside a model score without a factory.",
    )
    add_figure(
        doc,
        "fig-12-demo-simulation.png",
        "Figure 11. Recorded datasets stand in for sensors. REST and MQTT both enter telemetry_service.",
    )
    add_table(
        doc,
        ["Asset types", "Recording", "What “live” means in the demo"],
        [
            ["pump, cooling-system", "Kaggle pump-sensor, about 1-minute rows, 7 breakdowns", "Anonymized channels, rescaled to the model’s transform"],
            ["compressor", "MetroPT-3 metro air compressor, 5-minute averages, 4 air leaks", "Real oil temperature, pressure, and motor current"],
            ["motor, drive, conveyor", "NASA/IMS bearing rig, vibration RMS about every 10 minutes, 3 failures", "Gradual bearing wear, not a sudden leak"],
        ],
    )
    add_para(
        doc,
        "scripts/replay_telemetry.py asks the API which assets exist (GET /telemetry/ingest/targets), "
        "walks each asset’s clip, and sends one reading per asset per tick. The timestamp on the wire "
        "is “now”, so Monitoring looks live. The original time, units, dataset id, and ground-truth "
        "status travel in source_context. Assets that share a dataset start at different offsets so "
        "the plant is not all healthy or all failed at once. Default transport is REST batch. "
        "--transport mqtt publishes the same JSON to the broker. scripts/simulate_telemetry.py is a "
        "separate synthetic producer (healthy versus failing shapes), not a recording.",
    )
    add_para(
        doc,
        "Two ways to run the demo. Path A: no Docker, empty DATABASE_URL and REDIS_URL, embedded MQTT, "
        "SQLite, inline scoring. Path B: docker compose up -d (Timescale on host port 5433, Mosquitto "
        "1883, Redis 6379), set DATABASE_URL, MQTT_EMBEDDED=false, and REDIS_URL, then run uvicorn "
        "and python -m app.workers.scoring_worker. The frontend is always npm run dev in "
        "auravance-frontend, proxying /api to port 8000.",
    )

    add_heading(doc, "10. What is still pending", 1)
    add_bullets(
        doc,
        [
            "HA MQTT cluster, mTLS, and OT protocol adapters (OPC-UA, Sparkplug, historians).",
            "1M+ records/day, Timescale retention, compression, and continuous aggregates.",
            "pgvector for RAG; today vectors are JSON plus TF-IDF.",
            "A published, product-wide measured accuracy delta before any 30% claim.",
            "Auto work orders from alerts, CMMS integration, SSO, and multi-tenant isolation.",
            "Terraform still deploys Cloud Run + Firebase for a demo. It does not provision Timescale, Mosquitto, or Redis.",
        ],
    )

    add_heading(doc, "11. Related documents", 1)
    add_bullets(
        doc,
        [
            "docs/Auravance-Big-Picture.docx — this document",
            "docs/Auravance-Architecture.docx — longer illustrated architecture and deploy notes",
            "docs/Auravance-Business-and-How-It-Works.docx — business problem first",
            "docs/demo-backend-architecture.md — local stack",
            "docs/backend-architecture.md — production target",
            "README.md — commands for Path A and Path B",
        ],
    )

    footer = doc.add_paragraph()
    footer.paragraph_format.space_before = Pt(16)
    run = footer.add_run(
        "End of document. Generated from the repository as of 24 October 2026. "
        "Rebuild with python scripts/generate_architecture_diagrams.py and python scripts/generate_big_picture_docx.py."
    )
    set_run(run, italic=True, size=10, color=MUTED)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print(build())
