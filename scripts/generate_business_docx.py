"""Generate docs/Auravance-Business-and-How-It-Works.docx."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


BACKEND_DIR = Path(__file__).resolve().parents[1]
OUTPUT = BACKEND_DIR / "docs" / "Auravance-Business-and-How-It-Works.docx"
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
    section.top_margin = Inches(0.9)
    section.bottom_margin = Inches(0.9)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = title.add_run("Auravance")
    set_run(run, bold=True, size=26, color=NAVY)

    subtitle = doc.add_paragraph()
    run = subtitle.add_run("Business problem and how the system works")
    set_run(run, bold=True, size=16, color=TEAL)

    add_para(
        doc,
        "Written from the running code in auravance-backend and auravance-frontend. "
        "Date: 22 October 2026.",
        italic=True,
    )

    add_heading(doc, "1. Why this document exists", 1)
    add_para(
        doc,
        "This is an onboarding brief. Section 2 is the plant problem Auravance is built to "
        "solve. Section 3 onwards is how the software actually works today, including what is "
        "still a production target. It is not a resume substitute and it does not claim a "
        "product-wide 30% detection-accuracy improvement.",
    )

    add_heading(doc, "2. The business problem", 1)
    add_para(
        doc,
        "A process plant keeps value flowing through rotating and fluid equipment: pumps, "
        "air compressors, motors, drives, conveyors, cooling loops. When one of those assets "
        "fails without warning, the line stops. Production is lost, overtime and rush parts "
        "are expensive, and in some cases a bearing or seal failure is also a safety event. "
        "The economic question is not “can we buy a sensor?” — most plants already have "
        "temperature, vibration, pressure, and current readings. The question is whether "
        "anyone can turn those readings into a decision before the machine is already down.",
    )

    add_heading(doc, "2.1 Unplanned downtime is the expensive failure mode", 2)
    add_para(
        doc,
        "Run-to-failure is simple until it is not. A compressor air leak, a pump seal, or a "
        "motor bearing can look healthy on a shift checklist and then degrade in hours or "
        "days. The plant pays three times: lost throughput while the line is idle, premium "
        "repair cost because the job was not scheduled, and secondary damage because the "
        "first fault was allowed to run. Reliability teams already know this. What they lack "
        "is a consistent, asset-level signal that something has changed now, that failure is "
        "likely in the next shift or two, and roughly how many operating hours remain.",
    )

    add_heading(doc, "2.2 Calendar maintenance wastes work or still misses the failure", 2)
    add_para(
        doc,
        "The usual alternative is time-based preventive maintenance: rebuild the pump every "
        "N hours, grease the motor on a Friday, swap filters on a calendar. That policy "
        "over-services healthy machines (parts and labour spent too early) and still misses "
        "sudden faults such as a compressor leak that does not follow the calendar. Condition-"
        "based and predictive maintenance exist as ideas in most reliability programs. They "
        "fail in practice when the data is siloed in a historian, the model is a spreadsheet "
        "only one engineer trusts, or the “alert” is a raw threshold that cries wolf until "
        "operators ignore it.",
    )

    add_heading(doc, "2.3 Sensor data without a decision layer", 2)
    add_para(
        doc,
        "Four channels are enough to see many industrial faults if they are watched together: "
        "temperature, vibration, pressure, and current. Individually they are noisy. A current "
        "spike may be a load change. A temperature rise may be ambient. Vibration may be a "
        "passing truck. The business need is a layer that:",
    )
    add_bullets(
        doc,
        [
            "Ingests live readings from many assets without a custom dashboard per machine.",
            "Flags abnormal behaviour against that asset’s own recent history and type (pump vs compressor vs motor).",
            "Separates “this looks odd” (anomaly) from “this looks like a failure forming” (probability and remaining useful life).",
            "Does not go silent if a model file fails to load — operators still need a conservative reading.",
        ],
    )

    add_heading(doc, "2.4 Root cause is slow, tribal, and hard to audit", 2)
    add_para(
        doc,
        "When a high-risk label appears, the next cost is diagnosis time. The answer often "
        "lives in a vendor PDF, a site SOP, or a senior technician’s memory. Junior staff "
        "search folders; senior staff get pulled off the floor. Wrong first action — opening "
        "the wrong housing, changing oil instead of finding a leak — extends the outage. The "
        "business need is explainable diagnostics: likely causes and recommended actions that "
        "cite the manuals, tied to the same asset and sensor that just scored high-risk, "
        "with a fallback when the language model is unavailable.",
    )

    add_heading(doc, "2.5 Work still has to happen in the CMMS sense of the word", 2)
    add_para(
        doc,
        "A prediction that nobody can turn into a work order, a schedule, a defect record, or "
        "a vendor/equipment master is a science project. Plants already live in master data "
        "(plants, equipment, sensors, vendors) and execution records (schedules, work orders, "
        "defects). Auravance therefore includes those surfaces so a reliability engineer can "
        "move from “compressor-17 is high-risk, pressure is the dominant signal” to a tracked "
        "job. Auto-opening work orders from alerts is a later production step; the demo keeps "
        "prediction and execution adjacent but not auto-wired.",
    )

    add_heading(doc, "2.6 Who feels the pain", 2)
    add_table(
        doc,
        ["Role", "What hurts today", "What they need from Auravance"],
        [
            [
                "Reliability / process engineer",
                "Cannot see plant health in one console; models live in notebooks",
                "Live scores per asset, history charts, honest model status",
            ],
            [
                "Maintenance technician",
                "Alarm floods; RCA depends on who is on shift",
                "Dominant signal, grounded causes and actions, not a black-box score",
            ],
            [
                "Planner / supervisor",
                "Emergency work wrecks the weekly schedule",
                "72-hour failure probability and remaining useful life to pull work forward",
            ],
            [
                "Plant / IT admin",
                "Another silo, unclear who may ingest vs who may view",
                "User roles, ingest key separate from dashboard login, deployable demo",
            ],
        ],
    )

    add_heading(doc, "3. What Auravance is", 1)
    add_para(
        doc,
        "Auravance is a full-stack predictive maintenance platform for industrial equipment. "
        "The React console is the operator surface. The FastAPI service is the ingest, "
        "scoring, storage, and diagnostics engine. Together they give a plant a single place "
        "to watch assets, score incoming telemetry, raise alerts, and ask for root-cause "
        "guidance over equipment manuals.",
    )
    add_para(
        doc,
        "The intended product capability — the north star used as a build goal, not as a "
        "description of every line of code — is:",
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
        "Locally, the first three bullets are partially met: React + FastAPI monitoring is "
        "live; XGBoost and LSTM serve when artifacts load; MQTT exists as a local producer "
        "into the same ingest service; RAG over manuals is live with an OpenAI or playbook "
        "fallback. Timescale-scale ETL, an external plant MQTT cluster, and a product-wide "
        "30% accuracy claim are not shipped. Section 8 states the line clearly.",
    )

    add_heading(doc, "4. How a user moves through the product", 1)
    add_para(
        doc,
        "A reliability engineer signs in to the React console. The app loads plants, "
        "equipment, and assets, then polls the selected machine: last 24 telemetry points, "
        "latest prediction, and open alerts. Monitoring shows the four public channels, an "
        "anomaly label, 72-hour failure probability, estimated remaining useful life, and "
        "the dominant signal. If replay is feeding the plant, the original dataset’s ground "
        "truth (NORMAL, BROKEN, AIR_LEAK, FAILED, and similar) sits next to the model so "
        "the demo is honest.",
    )
    add_para(
        doc,
        "Root Cause Analysis is a deliberate action, not something that runs on every "
        "incoming reading. The technician submits the asset plus a symptom summary. The "
        "backend attaches the latest score, retrieves manual chunks, and returns likely "
        "causes and recommended actions. Master data and execution modules are CRUD against "
        "the same database: plants, vendors, equipment, schedules, work orders, defects. "
        "Admins manage users. The dashboard never posts ingest; live data comes from the "
        "simulator, the replay script, or MQTT.",
    )
    add_figure(
        doc,
        "fig-10-request-path.png",
        "Figure 1. After login the console loads catalogs, then polls live scores. RCA is an explicit POST.",
    )
    add_figure(
        doc,
        "fig-03-frontend-modules.png",
        "Figure 2. Console modules: Operations, Master Data, Execution, Admin.",
    )

    add_heading(doc, "5. How the system works technically", 1)
    add_heading(doc, "5.1 Two repositories, one HTTP contract", 2)
    add_para(
        doc,
        "auravance-frontend is a React 18 + Vite single-page app (localhost:5173 in "
        "development, with a proxy from /api to the API). auravance-backend is FastAPI on "
        "/api/v1 (localhost:8000). The frontend never embeds models. The backend never "
        "serves React sources. Production bakes VITE_API_BASE_URL at npm run build so the "
        "SPA calls Cloud Run directly.",
    )
    add_figure(
        doc,
        "fig-01-system-context.png",
        "Figure 3. Operators, replay scripts, FastAPI, SQLite, artifacts, and optional OpenAI.",
    )

    add_heading(doc, "5.2 End-to-end data path", 2)
    add_para(
        doc,
        "On a laptop the story is: a producer emits readings → FastAPI validates the asset "
        "and the four-channel payload → SQLite stores the row → scoring runs on the last "
        "eight points and may open an alert → the dashboard later asks for history (24 "
        "points) and a prediction on the last twelve points. RAG runs only when someone "
        "requests it.",
    )
    add_figure(
        doc,
        "fig-02-local-runtime.png",
        "Figure 4. Local processes: uvicorn :8000, Vite :5173, SQLite, optional MQTT on 1883.",
    )

    add_heading(doc, "5.3 Ingestion", 2)
    add_para(
        doc,
        "Every producer must finish in telemetry_service. That is the rule that keeps REST "
        "and MQTT honest: decode, map to the public payload, persist, score, maybe alert. "
        "Nothing bypasses scoring to write a “prediction” of its own.",
    )
    add_para(
        doc,
        '{ "timestamp": "...Z", "asset_id": "compressor-17", "metrics": { "temperature_c": 84.2, '
        '"vibration_rms": 0.63, "pressure_bar": 5.2, "current_a": 11.7 }, "source": "api", '
        '"source_context": {} }',
        italic=True,
    )
    add_bullets(
        doc,
        [
            "REST: POST /api/v1/telemetry/ingest and /ingest/batch (1–500 readings). Unknown asset IDs fail the whole batch (404).",
            "MQTT (local): topic plants/{plant_id}/lines/{line_id}/assets/{asset_id}/telemetry. Default is an embedded MQTT 3.1.1 broker (QoS 0) plus a paho-mqtt subscriber. This is a stand-in, not a plant broker cluster.",
            "Replay: scripts/replay_telemetry.py streams committed public-dataset clips as if the machines were live. source_context carries original timestamp, raw values, ground truth, units, and dataset id.",
            "Simulator: scripts/simulate_telemetry.py posts synthetic healthy/failing readings.",
            "Alert cooldown: AURAVANCE_ALERT_COOLDOWN_SECONDS (default 300) unless severity rises.",
        ],
    )
    add_figure(
        doc,
        "fig-04-ingestion.png",
        "Figure 5. REST and MQTT are producers. Persistence, scoring, and cooldown live in telemetry_service.",
    )

    add_heading(doc, "5.4 The four channels and three equipment profiles", 2)
    add_para(
        doc,
        "The public wire format is fixed at four metrics so the dashboard, SQLite columns, "
        "and all three model profiles stay in lockstep. Expanding a fifth channel is a "
        "cross-repo change, not a local tweak.",
    )
    add_table(
        doc,
        ["Asset types", "Profile", "Training / replay source", "Failure character"],
        [
            ["pump, cooling-system", "pump", "Kaggle pump-sensor (1 min)", "Mixed; 72-hour forecast is weak"],
            ["compressor", "compressor", "MetroPT-3 air compressor (5 min)", "Sudden air leaks; leak-in-progress is learnable"],
            ["motor, drive, conveyor", "motor", "NASA/IMS bearing run-to-failure (10 min RMS)", "Gradual bearing degradation"],
        ],
    )

    add_heading(doc, "5.5 Storage", 2)
    add_para(
        doc,
        "The demo store is SQLite at data/auravance_demo.db (WAL mode so the API thread and "
        "MQTT subscriber can share it). init_db() creates tables and seeds demo plants, "
        "assets, users, vendors, equipment, schedules, work orders, and defects. Schema "
        "changes belong in app/core/db.py together with seed data. This is not TimescaleDB "
        "and not pgvector. Cloud Run has no volume in the current Terraform, so the file "
        "inside a container is ephemeral after a new revision.",
    )
    add_figure(
        doc,
        "fig-07-sqlite.png",
        "Figure 6. Implemented SQLite groups. Dashed boxes are the production storage target.",
    )

    add_heading(doc, "5.6 Scoring: anomaly, failure, remaining useful life", 2)
    add_para(
        doc,
        "Three questions stay separate on purpose. Mixing them is how demo platforms lie.",
    )
    add_bullets(
        doc,
        [
            "Anomaly — “does this look unlike healthy operation?” Isolation Forest on healthy data, else a rules mix of normalized channels and trend.",
            "Failure — “is this failing now, or likely within 72 hours?” LSTM sequence (window 12) if history and artifact are present; else XGBoost tabular; else HistGradientBoosting; else rules.",
            "RUL — “about how many hours until the next failure?” XGBoost if present, else HistGradientBoosting, else a value derived from failure probability (capped). Do not reuse a classification score as RUL except the documented compressor sudden-failure wrappers.",
        ],
    )
    add_para(
        doc,
        "score_asset() in app/services/scoring.py picks the profile from asset type, loads "
        "artifacts (joblib dict, artifact_schema_version: 1), and always has a rules "
        "fallback so a missing or unloadable model does not take the API down. "
        "fallback_active is visible on GET /predictions/models/status. Replay honesty: if "
        "source_context.dataset matches a training fold and the timestamp is in a held-out "
        "window, the API serves the stored +heldout-N estimator instead of the full-fit "
        "model that already saw that failure.",
    )
    add_figure(
        doc,
        "fig-05-scoring.png",
        "Figure 7. Isolation Forest, LSTM then XGBoost/HGB, RUL model, rules if artifacts fail to load.",
    )
    add_para(
        doc,
        "Measured detection delta versus the rules scorer on replay clips lives in "
        "artifacts/models/detection_delta.json. Pump tabular ROC-AUC is high against a weak "
        "anonymized-channel rules baseline; compressor is about +20% versus a stronger "
        "rules baseline; motor snapshots after downsampling are too sparse for a 30% claim "
        "(and tabular AUC there is not a win). Do not quote a product-wide 30% improvement.",
        italic=True,
    )

    add_heading(doc, "5.7 RAG diagnostics", 2)
    add_para(
        doc,
        "POST /diagnostics/root-cause takes asset_id, a symptom summary, and optional alert "
        "ids. The service loads the latest prediction, maps dominant_signal onto a local "
        "issue playbook, retrieves about five knowledge chunks (OpenAI embeddings when "
        "OPENAI_API_KEY is set, otherwise TF-IDF over SQLite), then calls the OpenAI "
        "Responses API with a JSON schema at low temperature. If the key or the API is "
        "down, it extracts cause and action sentences from the chunks plus the playbook. "
        "Status reports openai_api_key_loaded as a boolean only — the key is never echoed. "
        "Index the corpus with python scripts/prepare_knowledge.py over knowledge/raw PDFs "
        "and knowledge/*.md guides.",
    )
    add_figure(
        doc,
        "fig-06-rag.png",
        "Figure 8. RCA is request-driven. Retrieval and generation both have a local fallback.",
    )

    add_heading(doc, "5.8 Auth: dashboard login is not ingest", 2)
    add_bullets(
        doc,
        [
            "People: POST /auth/login returns a JWT. Subsequent console calls send Authorization: Bearer. Demo admin is seeded in SQLite (see README / .env.example).",
            "Machines: X-Ingest-Key on ingest routes when AURAVANCE_INGEST_API_KEY is set. Unset keeps ingest open for local development.",
            "A dashboard JWT cannot replace the ingest key, and the ingest key cannot log into the console.",
        ],
    )

    add_heading(doc, "5.9 Contracts the frontend depends on", 2)
    add_para(
        doc,
        "Additive fields are acceptable. Renaming or removing these requires a lockstep "
        "change in auravance-frontend.",
    )
    add_table(
        doc,
        ["Contract", "Must stay stable"],
        [
            ["Telemetry ingest", "Four metric keys; source_context preserved on replay"],
            [
                "Prediction latest",
                "anomaly_score/label, failure_probability_72h, estimated_rul_hours, dominant_signal, model versions",
            ],
            [
                "RAG root-cause",
                "likely_causes, recommended_actions, grounded_summary, evidence_snippets, generation_mode",
            ],
            ["Auth", "POST /auth/login → access_token; Bearer thereafter"],
        ],
    )

    add_heading(doc, "6. Demo plant vs a real plant", 1)
    add_para(
        doc,
        "A real plant would publish from PLCs and IoT gateways into an MQTT cluster, land "
        "time-series in TimescaleDB, and keep RAG vectors in pgvector. This repo’s demo "
        "substitutes replay of public run-to-failure datasets so the scoring path, alerts, "
        "and dashboard can be exercised without factory hardware. Each registered asset "
        "gets the dataset that matches its type; assets that share a dataset start at "
        "offset positions so the plant is not all “healthy” or all “failed” at once. "
        "Timestamps on the wire are “now”; the original time and ground truth travel in "
        "source_context.",
    )
    add_para(
        doc,
        "That substitution is why MQTT in this tree is an extra local producer, not proof "
        "of 1M+ records/day. High-volume ETL is still offline scripts (prepare_datasets.py, "
        "prepare_metropt.py, prepare_ims.py, build_replay_dataset.py) plus SQLite inserts.",
    )

    add_heading(doc, "7. Deploy shape (demo, not production HA)", 1)
    add_para(
        doc,
        "Docker: python:3.11-slim, pip install -e ., uvicorn on $PORT. The image does not "
        "include the optional torch extra or a durable data/ volume. Terraform under "
        "terraform/ creates Artifact Registry, Secret Manager (openai-api-key), Cloud Run "
        "v2 (min 0, max 2, 1 vCPU / 512Mi), and a Firebase Hosting site resource. You still "
        "build and push the image, set VITE_API_BASE_URL, npm run build, and firebase deploy. "
        "Health check {backend_url}/api/v1/health. terraform.tfvars stays gitignored. This "
        "layout is a free-tier portfolio deploy: no Cloud SQL, no MQTT broker, no Redis, no CI.",
    )
    add_figure(
        doc,
        "fig-08-deploy.png",
        "Figure 9. Docker image to Artifact Registry to Cloud Run; SPA on Firebase Hosting.",
    )

    add_heading(doc, "8. Implemented today versus production target", 1)
    add_figure(
        doc,
        "fig-09-current-vs-target.png",
        "Figure 10. Solid boxes are in these repos. Dashed boxes remain the documented target.",
    )
    add_table(
        doc,
        ["Need", "In the repos today", "Still a target"],
        [
            ["Watch the plant", "React console + FastAPI /api/v1", "Hardened auth, tenancy, push (WebSocket/SSE)"],
            ["Get data in", "REST ingest + local MQTT subscriber / embedded broker", "External MQTT cluster, 1M+ records/day"],
            ["Keep history", "SQLite WAL demo DB", "PostgreSQL + TimescaleDB"],
            ["Score risk", "Isolation Forest; XGBoost or HGB; LSTM beside tabular; rules fallback", "Same algorithms, production serving and monitoring"],
            ["Explain the fault", "OpenAI or TF-IDF retrieval + playbook fallback", "pgvector index, stronger evidence"],
            ["Prove 30% better detection", "evaluate_detection_delta.py vs rules; mixed by profile", "A published, product-wide measured delta"],
        ],
    )

    add_heading(doc, "9. How to see it run", 1)
    add_para(
        doc,
        "From auravance-backend: create a Python 3.12 venv, pip install -e \".[sequence]\", "
        "copy .env.example to .env, then uvicorn app.main:app --reload --host 127.0.0.1 "
        "--port 8000. From auravance-frontend: npm run dev (Vite :5173). Optionally "
        "python scripts/replay_telemetry.py to stream the demo plant. Open the console, "
        "sign in with the seeded demo admin, and use Monitoring then Root Cause Analysis. "
        "uvicorn --reload restarts the process and drops the embedded MQTT broker; REST "
        "replay is more reliable while developing. Tests: pytest tests/.",
    )

    add_heading(doc, "10. Related documents", 1)
    add_bullets(
        doc,
        [
            "docs/Auravance-Architecture.docx — illustrated architecture (ingest, SQLite, scoring, RAG, Docker, Terraform)",
            "docs/demo-backend-architecture.md — local stack",
            "docs/backend-architecture.md — production target",
            "README.md — run, train, replay",
            "auravance-frontend/README.md — Vite proxy and production API URL",
        ],
    )

    footer = doc.add_paragraph()
    footer.paragraph_format.space_before = Pt(18)
    run = footer.add_run(
        "End of document. Generated from the repository layout as of 22 October 2026."
    )
    set_run(run, italic=True, size=10, color=MUTED)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print(build())
