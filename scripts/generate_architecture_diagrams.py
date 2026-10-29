"""Render architecture PNGs for the Word document. Labels match implemented code."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle


OUT = Path(__file__).resolve().parents[1] / "docs" / "architecture-diagrams"
NAVY = "#0B2E4A"
TEAL = "#0D6E7A"
ORANGE = "#C45C26"
GOLD = "#C4A35A"
SLATE = "#5A6A7A"
GREEN = "#2F6F4E"
WHITE = "#FFFFFF"
PAPER = "#F7F4EE"
DASH = "#9AA7B2"


def new_fig(width=13.2, height=7.4):
    fig, ax = plt.subplots(figsize=(width, height), dpi=160)
    fig.patch.set_facecolor(PAPER)
    ax.set_facecolor(PAPER)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, title, subtitle="", *, fill=TEAL, title_size=9.5, sub_size=7.5, edge=None):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.3,rounding_size=1.2",
        linewidth=1.2,
        edgecolor=edge or NAVY,
        facecolor=fill,
    )
    ax.add_patch(patch)
    if subtitle:
        title_y = y + h * (0.78 if h >= 28 else 0.62)
        sub_y = y + h * (0.42 if h >= 28 else 0.28)
        ax.text(x + w / 2, title_y, title, ha="center", va="center", color=WHITE, fontsize=title_size, fontweight="bold")
        ax.text(x + w / 2, sub_y, subtitle, ha="center", va="center", color=WHITE, fontsize=sub_size, alpha=0.95)
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", color=WHITE, fontsize=title_size, fontweight="bold")
    return (x + w / 2, y + h / 2, x, y, w, h)


def ghost(ax, x, y, w, h, title, subtitle="not built"):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.3,rounding_size=1.2",
        linewidth=1.4,
        linestyle=(0, (4, 3)),
        edgecolor=DASH,
        facecolor="#E8EDF1",
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h * 0.62, title, ha="center", va="center", color=SLATE, fontsize=9, fontweight="bold")
    ax.text(x + w / 2, y + h * 0.28, subtitle, ha="center", va="center", color=SLATE, fontsize=7.5)


def arrow(ax, p1, p2, text="", *, color=NAVY, rad=0.0, dy=2.2):
    ax.add_patch(
        FancyArrowPatch(
            p1,
            p2,
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=1.4,
            color=color,
            shrinkA=2,
            shrinkB=2,
            connectionstyle=f"arc3,rad={rad}",
        )
    )
    if text:
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        ax.text(mx, my + dy, text, ha="center", va="bottom", fontsize=7.2, color=color, fontweight="bold")


def banner(ax, text):
    ax.text(50, 96.5, text, ha="center", va="top", fontsize=15, fontweight="bold", color=NAVY)


def note(ax, text, y=3.2):
    ax.text(50, y, text, ha="center", va="center", fontsize=8, color=SLATE, style="italic")


def save(fig, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def fig_system_context():
    fig, ax = new_fig()
    banner(ax, "Figure 1. System context — two repositories, one HTTP contract")
    box(ax, 4, 70, 18, 16, "Reliability\nengineer", "browser", fill=SLATE)
    box(ax, 38, 70, 24, 16, "auravance-frontend", "React 18 + Vite  :5173", fill=ORANGE)
    box(ax, 72, 70, 24, 16, "auravance-backend", "FastAPI  /api/v1  :8000", fill=TEAL)
    arrow(ax, (22, 78), (38, 78), "HTTPS / Vite proxy")
    arrow(ax, (62, 78), (72, 78), "JWT + JSON")

    box(ax, 4, 38, 22, 18, "Replay / simulator", "scripts/*.py\nREST or MQTT", fill=GOLD)
    box(ax, 38, 38, 24, 18, "Ingest + scoring", "telemetry_service\nscore_asset()", fill=TEAL)
    box(ax, 72, 38, 24, 18, "SQLite demo DB", "data/auravance_demo.db", fill=NAVY)
    arrow(ax, (26, 47), (38, 47), "readings")
    arrow(ax, (62, 47), (72, 47), "persist")
    arrow(ax, (84, 56), (84, 70), "reads")
    arrow(ax, (50, 56), (50, 70), "predictions / RAG")

    box(ax, 8, 10, 20, 16, "Knowledge files", "manuals + guides", fill=GREEN)
    box(ax, 40, 10, 20, 16, "Model artifacts", "joblib + JSON", fill=GREEN)
    box(ax, 72, 10, 20, 16, "OpenAI (optional)", "embeddings + RCA", fill=GREEN)
    arrow(ax, (18, 26), (48, 38), "")
    arrow(ax, (50, 26), (50, 38), "")
    arrow(ax, (82, 26), (84, 38), "")
    note(ax, "The dashboard never embeds models. The backend never serves React sources.")
    return save(fig, "fig-01-system-context.png")


def fig_local_runtime():
    fig, ax = new_fig(13.2, 8.2)
    banner(ax, "Figure 2. Local runtime — what you start on a laptop")
    box(ax, 3, 72, 28, 14, "replay_telemetry.py", "--transport rest | mqtt", fill=GOLD)
    box(ax, 36, 72, 28, 14, "simulate_telemetry.py", "synthetic healthy / failing", fill=GOLD)
    box(ax, 69, 72, 28, 14, "npm run dev", "localhost:5173  proxy /api", fill=ORANGE)

    box(ax, 26, 42, 56, 20, "FastAPI  uvicorn :8000", "lifespan: init_db()  +  start_mqtt()   CORS *   /api/v1", fill=TEAL)
    arrow(ax, (22, 72), (40, 62), "REST batch")
    arrow(ax, (50, 72), (50, 62), "REST ingest")
    arrow(ax, (83, 72), (70, 62), "JWT reads")

    box(ax, 3, 12, 22, 18, "Embedded MQTT", "127.0.0.1:1883\nlocal only", fill=NAVY)
    box(ax, 28, 12, 22, 18, "SQLite + WAL", "assets, telemetry,\nalerts, master data", fill=NAVY)
    box(ax, 53, 12, 22, 18, "Scoring", "IF + XGB/HGB + LSTM\nrules fallback", fill=GREEN)
    box(ax, 78, 12, 19, 18, "RAG", "TF-IDF / OpenAI\n+ playbook", fill=GREEN)
    arrow(ax, (10, 72), (14, 30), "MQTT publish", rad=-0.15, dy=-8)
    arrow(ax, (14, 30), (38, 42), "subscribe", rad=0.05, dy=1.0)
    arrow(ax, (40, 42), (39, 30), "store")
    arrow(ax, (50, 42), (64, 30), "score")
    arrow(ax, (70, 42), (88, 30), "on request")
    note(ax, "MQTT is an extra producer into telemetry_service. REST ingest stays for replay while uvicorn --reload is on.")
    return save(fig, "fig-02-local-runtime.png")


def fig_frontend():
    fig, ax = new_fig()
    banner(ax, "Figure 3. Frontend console — src/App.jsx modules")
    box(ax, 6, 78, 88, 10, "Login  →  JWT in localStorage key auravance.currentUser", "POST /auth/login     then Bearer on every read/write", fill=NAVY, title_size=11)
    groups = [
        (6, "Operations", ORANGE, ["Monitoring", "Root Cause Analysis"]),
        (30, "Master data", TEAL, ["Plant Info", "Equipment", "Vendors"]),
        (54, "Execution", GREEN, ["Schedules", "Work orders", "Defects"]),
        (78, "Admin", SLATE, ["Users\n(Admin only)"]),
    ]
    for x, title, color, items in groups:
        box(ax, x, 52, 16, 18, title, fill=color)
        for i, item in enumerate(items):
            box(ax, x, 40 - i * 11, 16, 9.5, item, fill="#3D7A86" if color == TEAL else color, title_size=8)

    box(ax, 6, 2, 88, 10, "API_BASE_URL = VITE_API_BASE_URL ?? \"/api/v1\"", "Local proxy: /api  →  http://127.0.0.1:8000     Production: Cloud Run URL baked in at npm run build", fill=SLATE, title_size=10)
    note(ax, "Four telemetry cards: temperature_c, vibration_rms, pressure_bar, current_a. Replay ground truth is shown from source_context.", y=0.8)
    return save(fig, "fig-03-frontend-modules.png")


def fig_ingest():
    fig, ax = new_fig(13.2, 8.0)
    banner(ax, "Figure 4. Ingestion pipeline — every producer ends in telemetry_service")
    box(ax, 3, 72, 22, 16, "REST simulator", "POST /ingest", fill=GOLD)
    box(ax, 3, 50, 22, 16, "REST replay", "POST /ingest/batch", fill=GOLD)
    box(ax, 3, 22, 22, 16, "MQTT replay", "topic per asset", fill=GOLD)

    box(ax, 30, 22, 18, 16, "MQTT broker", "embedded local\nor external later", fill=NAVY)
    arrow(ax, (25, 30), (30, 30), "")
    arrow(ax, (48, 30), (56, 48), "decode JSON", rad=-0.12, dy=-0.4)

    box(ax, 56, 40, 20, 32, "telemetry_service", "validate asset\nwrite SQLite\nscore last 8\nalert + cooldown", fill=TEAL, title_size=10)
    arrow(ax, (25, 80), (56, 66), "REST", rad=0.08)
    arrow(ax, (25, 58), (56, 58), "REST")

    box(ax, 82, 70, 15, 14, "telemetry", "4 channels +\nsource_context", fill=NAVY, title_size=8.5)
    box(ax, 82, 50, 15, 14, "alerts", "cooldown 300s\nunless severity rises", fill=ORANGE, title_size=8.5)
    box(ax, 82, 30, 15, 14, "predictions", "on GET latest\nlast 12 points", fill=GREEN, title_size=8.5)
    arrow(ax, (76, 66), (82, 77), "persist", dy=0.4)
    arrow(ax, (76, 58), (82, 57), "maybe alert", dy=1.6)
    arrow(ax, (76, 48), (82, 37), "dashboard", dy=-3.5)
    ax.text(50, 18, "Topic:  plants/{plant_id}/lines/{line_id}/assets/{asset_id}/telemetry", ha="center", fontsize=9, color=NAVY, fontweight="bold")
    ax.text(50, 12, "Payload: timestamp, asset_id, metrics{temperature_c, vibration_rms, pressure_bar, current_a}, source, source_context", ha="center", fontsize=8, color=SLATE)
    note(ax, "Unknown asset IDs fail a whole batch (404). Ingest key X-Ingest-Key is separate from dashboard JWT.")
    return save(fig, "fig-04-ingestion.png")


def fig_scoring():
    fig, ax = new_fig(13.2, 8.0)
    banner(ax, "Figure 5. Scoring path — Isolation Forest, XGBoost/HGB, LSTM, rules fallback")
    box(ax, 4, 72, 28, 16, "Last N telemetry rows", "alerts: 8     dashboard: 12", fill=GOLD)
    box(ax, 38, 72, 24, 16, "profile_for_asset", "pump / compressor / motor", fill=TEAL)
    arrow(ax, (32, 80), (38, 80), "")

    box(ax, 4, 42, 20, 18, "Isolation Forest", "anomaly score\n+ dominant signal", fill=NAVY)
    box(ax, 28, 42, 20, 18, "Tabular failure", "XGBoost if present\nelse HistGB", fill=TEAL)
    box(ax, 52, 42, 20, 18, "LSTM sequence", "window=12\nif torch + artifact", fill=GREEN)
    box(ax, 76, 42, 20, 18, "RUL model", "XGBoost or HGB\nhours, cap 240", fill=ORANGE)
    arrow(ax, (50, 72), (14, 60), "")
    arrow(ax, (50, 72), (38, 60), "")
    arrow(ax, (50, 72), (62, 60), "")
    arrow(ax, (50, 72), (86, 60), "")

    box(ax, 18, 12, 64, 18, "score_asset()  →  PredictionResponse", "anomaly_label   failure_probability_72h   estimated_rul_hours   dominant_signal   model versions", fill=NAVY, title_size=11)
    arrow(ax, (14, 42), (36, 30), "")
    arrow(ax, (38, 42), (44, 30), "if LSTM unavailable")
    arrow(ax, (62, 42), (50, 30), "preferred when window full")
    arrow(ax, (86, 42), (64, 30), "")
    box(ax, 4, 14, 12, 14, "Rules", "if models\nfail to load", fill=SLATE, title_size=8)
    arrow(ax, (16, 21), (18, 21), "")
    note(ax, "Replay honesty: source_context.dataset matching a training fold uses +heldout-N, not the full-fit estimator.")
    return save(fig, "fig-05-scoring.png")


def fig_rag():
    fig, ax = new_fig()
    banner(ax, "Figure 6. RAG root-cause analysis — request-driven, not on the ingest hot path")
    box(ax, 4, 72, 28, 16, "Technician / dashboard", "POST /diagnostics/root-cause", fill=ORANGE)
    box(ax, 40, 72, 24, 16, "Latest prediction", "label, 72h risk, RUL,\ndominant_signal", fill=TEAL)
    box(ax, 72, 72, 24, 16, "Symptom summary", "built from prediction\n+ recent alerts", fill=GOLD)
    arrow(ax, (32, 80), (40, 80), "")
    arrow(ax, (64, 80), (72, 80), "")

    box(ax, 8, 42, 84, 18, "knowledge_service.retrieve", "OpenAI query embedding if OPENAI_API_KEY is set, else TF-IDF over SQLite chunks   limit default 5", fill=NAVY, title_size=11)
    arrow(ax, (54, 72), (50, 60), "query")

    box(ax, 8, 14, 38, 18, "OpenAI Responses API", "JSON schema, temp 0.2\ngrounded in evidence only", fill=GREEN)
    box(ax, 54, 14, 38, 18, "Playbook fallback", "ISSUE_PLAYBOOK + keyword\nsentences from chunks", fill=SLATE)
    arrow(ax, (30, 42), (27, 32), "key present")
    arrow(ax, (70, 42), (73, 32), "key missing / error")
    note(ax, "Status reports openai_api_key_loaded as a boolean only. pgvector is the documented next index.")
    return save(fig, "fig-06-rag.png")


def fig_sqlite():
    fig, ax = new_fig(13.2, 8.0)
    banner(ax, "Figure 7. SQLite demo store — groups of tables in data/auravance_demo.db")
    groups = [
        (4, TEAL, "Telemetry path", "assets\ntelemetry\nalerts"),
        (28, NAVY, "Master data", "plants\nvendors\nequipment\nsensors\nusers"),
        (52, ORANGE, "Execution", "maintenance_schedules\nwork_orders\ndefects"),
        (76, GREEN, "Catalog / RAG", "dataset_catalog\nknowledge docs\nchunks / vectors"),
    ]
    for x, color, title, body in groups:
        box(ax, x, 38, 20, 42, title, body, fill=color, title_size=11, sub_size=8.5)
    ax.text(50, 28, "telemetry row: asset_id, timestamp, temperature_c, vibration_rms, pressure_bar, current_a, source, source_context_json", ha="center", fontsize=8.5, color=NAVY)
    ax.text(50, 22, "Index: (asset_id, timestamp)     PRAGMA journal_mode=WAL     init_db() seeds demo plants and users", ha="center", fontsize=8.5, color=SLATE)

    ghost(ax, 10, 6, 36, 12, "PostgreSQL + TimescaleDB", "production telemetry target")
    ghost(ax, 54, 6, 36, 12, "pgvector", "production RAG index target")
    note(ax, "Cloud Run has no volume in Terraform — SQLite inside the container is ephemeral after a new revision.", y=2.4)
    return save(fig, "fig-07-sqlite.png")


def fig_deploy():
    fig, ax = new_fig(13.2, 8.2)
    banner(ax, "Figure 8. Demo deploy on GCP — Docker, Terraform, Firebase CLI")
    box(ax, 4, 70, 28, 18, "Dockerfile", "python:3.11-slim\npip install -e .\nuvicorn :$PORT", fill=NAVY)
    box(ax, 36, 70, 28, 18, "Artifact Registry", "docker push\n…/auravance/backend:latest", fill=TEAL)
    box(ax, 68, 70, 28, 18, "Cloud Run v2", "min 0  max 2\n1 vCPU / 512Mi\npublic invoker optional", fill=ORANGE)
    arrow(ax, (32, 79), (36, 79), "build")
    arrow(ax, (64, 79), (68, 79), "image")

    box(ax, 4, 38, 28, 18, "Terraform apply", "apis, registry, secrets,\nCloud Run, Hosting site", fill=TEAL)
    box(ax, 36, 38, 28, 18, "Secret Manager", "openai-api-key\nbackend SA accessor", fill=GREEN)
    box(ax, 68, 38, 28, 18, "Firebase Hosting", "SPA from frontend\nnpm run build → dist", fill=ORANGE)
    arrow(ax, (18, 56), (50, 70), "creates registry", rad=0.2, dy=0.6)
    arrow(ax, (50, 56), (82, 70), "inject env", rad=0.18, dy=1.2)
    arrow(ax, (82, 56), (82, 70), "HTTPS /api/v1")

    box(ax, 10, 10, 80, 16, "Not in this Terraform", "No Cloud SQL/Timescale  ·  No MQTT broker  ·  No Redis  ·  No CI  ·  SQLite is not durable on Cloud Run", fill=SLATE, title_size=11)
    note(ax, "Health check the deployed API at {backend_url}/api/v1/health. terraform.tfvars stays gitignored.")
    return save(fig, "fig-08-deploy.png")


def fig_current_vs_target():
    fig, ax = new_fig(13.4, 8.4)
    banner(ax, "Figure 9. Implemented local stack versus production target")
    ax.add_patch(Rectangle((3, 8), 45, 80, fill=True, facecolor="#E7F1F3", edgecolor=TEAL, linewidth=1.4))
    ax.add_patch(Rectangle((52, 8), 45, 80, fill=True, facecolor="#F1F1F3", edgecolor=DASH, linewidth=1.4, linestyle=(0, (4, 3))))
    ax.text(25.5, 84, "TODAY (this repo)", ha="center", fontsize=12, fontweight="bold", color=TEAL)
    ax.text(74.5, 84, "TARGET (not built)", ha="center", fontsize=12, fontweight="bold", color=SLATE)

    today = [
        (70, "Replay / REST / local MQTT"),
        (58, "FastAPI monolith  /api/v1"),
        (46, "SQLite + WAL"),
        (34, "IF + XGBoost/HGB + LSTM"),
        (22, "TF-IDF / OpenAI RAG"),
        (10, "Cloud Run + Firebase demo"),
    ]
    target = [
        (70, "Plant sensors → MQTT cluster"),
        (58, "Ingest + stream processing"),
        (46, "TimescaleDB + PostgreSQL"),
        (34, "Same models, production serving"),
        (22, "RAG over pgvector"),
        (10, "HA, tenancy, 1M+ records/day"),
    ]
    for y, label in today:
        box(ax, 8, y, 35, 10, label, fill=TEAL, title_size=9)
    for y, label in target:
        ghost(ax, 57, y, 35, 10, label, "docs/backend-architecture.md")
    note(ax, "Upgrade order already followed locally: REST stays, MQTT added, XGBoost served, LSTM beside tabular. Next: TimescaleDB, then a measured accuracy delta.")
    return save(fig, "fig-09-current-vs-target.png")


def fig_request_path():
    fig, ax = new_fig(13.2, 6.6)
    banner(ax, "Figure 10. Dashboard request path after login")
    steps = [
        (3, "1. Login", "POST /auth/login"),
        (22, "2. Session", "JWT in localStorage"),
        (41, "3. Catalog", "GET assets, plants,\nequipment, …"),
        (60, "4. Live view", "GET telemetry/history\nGET predictions/latest"),
        (79, "5. RCA", "POST diagnostics/\nroot-cause"),
    ]
    for x, title, sub in steps:
        box(ax, x, 38, 17, 28, title, sub, fill=TEAL if x < 70 else GREEN, title_size=10)
    for x in (20, 39, 58, 77):
        arrow(ax, (x, 52), (x + 2, 52), "")
    ax.text(50, 22, "Monitoring polls history (limit 24) and latest prediction for the selected asset.", ha="center", fontsize=9, color=NAVY)
    ax.text(50, 16, "RCA is explicit (button). Scoring on ingest is automatic. Diagnostics never run inside the MQTT/REST hot path.", ha="center", fontsize=8.5, color=SLATE)
    note(ax, "Ingest producers use X-Ingest-Key. The dashboard never calls ingest.")
    return save(fig, "fig-10-request-path.png")


def fig_enterprise_sensors():
    fig, ax = new_fig(13.2, 8.2)
    banner(ax, "Figure 11. How live sensors would enter — same contract the code already accepts")
    box(ax, 3, 74, 22, 14, "PLC / sensor", "temp, vibration,\npressure, current", fill=SLATE, title_size=9)
    box(ax, 30, 74, 28, 14, "Edge gateway", "map tags → 4 channels\npublish JSON", fill=GOLD, title_size=9)
    box(ax, 64, 74, 32, 14, "MQTT broker", "Mosquitto today\nHA cluster later", fill=NAVY, title_size=9)
    arrow(ax, (25, 81), (30, 81), "")
    arrow(ax, (58, 81), (64, 81), "topic")

    box(ax, 8, 46, 36, 16, "FastAPI subscriber", "decode topic + JSON\ntelemetry_service.ingest", fill=TEAL, title_size=10)
    box(ax, 52, 46, 40, 16, "Timescale telemetry", "hypertable on timestamp\nfour channels + context", fill=NAVY, title_size=10)
    arrow(ax, (80, 74), (70, 62), "subscribe")
    arrow(ax, (44, 54), (52, 54), "persist")

    box(ax, 8, 18, 28, 16, "Scoring worker", "Redis queue\nlast 8 → alert", fill=GREEN, title_size=9)
    box(ax, 42, 18, 24, 16, "Dashboard", "JWT polls history\nand latest score", fill=ORANGE, title_size=9)
    box(ax, 70, 18, 26, 16, "RCA on request", "manuals + prediction\nnot on ingest", fill=GREEN, title_size=9)
    arrow(ax, (22, 46), (22, 34), "enqueue")
    arrow(ax, (62, 46), (54, 34), "read")
    ax.text(
        50,
        10,
        "Topic: plants/{plant_id}/lines/{line_id}/assets/{asset_id}/telemetry     Asset must already exist or the batch is 404.",
        ha="center",
        fontsize=8,
        color=NAVY,
    )
    note(ax, "REST POST /telemetry/ingest is the same door if a site cannot publish MQTT. OPC-UA and Sparkplug adapters are not in this repo.")
    return save(fig, "fig-11-enterprise-sensors.png")


def fig_demo_simulation():
    fig, ax = new_fig(13.2, 8.0)
    banner(ax, "Figure 12. Demo stand-in — recorded machines, not a live plant")
    box(ax, 4, 70, 28, 16, "Public recordings", "Kaggle pump\nMetroPT-3\nNASA/IMS", fill=GOLD, title_size=9)
    box(ax, 38, 70, 28, 16, "Prepare scripts", "data/replay clips\ncommitted", fill=TEAL, title_size=9)
    box(ax, 72, 70, 24, 16, "replay_telemetry.py", "stamp time = now\nkeep ground truth", fill=ORANGE, title_size=9)
    arrow(ax, (32, 78), (38, 78), "")
    arrow(ax, (66, 78), (72, 78), "")

    box(ax, 8, 40, 36, 16, "REST batch", "POST /ingest/batch\ndefault transport", fill=NAVY, title_size=10)
    box(ax, 56, 40, 36, 16, "MQTT publish", "--transport mqtt\nsame JSON payload", fill=NAVY, title_size=10)
    arrow(ax, (80, 70), (26, 56), "rest")
    arrow(ax, (84, 70), (74, 56), "mqtt")

    box(ax, 16, 12, 68, 16, "Same telemetry_service as a real gateway", "SQLite or Timescale   ·   score inline or worker   ·   dashboard shows model next to NORMAL / AIR_LEAK / FAILED", fill=TEAL, title_size=10)
    arrow(ax, (26, 40), (40, 28), "")
    arrow(ax, (74, 40), (60, 28), "")
    note(ax, "simulate_telemetry.py is synthetic. Replay is recorded. Neither is a PLC.")
    return save(fig, "fig-12-demo-simulation.png")


def main() -> list[Path]:
    paths = [
        fig_system_context(),
        fig_local_runtime(),
        fig_frontend(),
        fig_ingest(),
        fig_scoring(),
        fig_rag(),
        fig_sqlite(),
        fig_deploy(),
        fig_current_vs_target(),
        fig_request_path(),
        fig_enterprise_sensors(),
        fig_demo_simulation(),
    ]
    for path in paths:
        print(path)
    return paths


if __name__ == "__main__":
    main()
