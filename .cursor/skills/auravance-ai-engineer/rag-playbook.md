# Auravance RAG playbook

Read this when changing diagnostics, knowledge indexing, or OpenAI calls.

## Purpose

Turn a scored asset (anomaly label, dominant signal, 72h risk, RUL) plus a
technician symptom summary into **grounded** likely causes and maintenance
actions, citing equipment manuals and internal guides.

## Indexing

```bash
python scripts/prepare_knowledge.py
```

Sources:

- PDFs under `knowledge/raw/{vendor}/*.pdf` (e.g. `valeo/`)
- Built-in markdown under `knowledge/*.md` (playbook, compressor,
  bearing, motor, temperature guides)

Pipeline in `prepare_knowledge.py`:

1. Extract text (`pypdf` or markdown).
2. Write normalized files to `knowledge/processed`.
3. Chunk ~1200 chars with 200 overlap → `knowledge/chunks` JSONL.
4. Build corpus TF-IDF-style vectors for local search.
5. If `OPENAI_API_KEY` is set, embed with `AURAVANCE_RAG_EMBEDDING_MODEL`
   (default `text-embedding-3-small`, 1536 dims) and store vectors in SQLite.

Inspect: `GET /api/v1/knowledge/documents`,
`GET /api/v1/knowledge/search?q=bearing%20temperature`,
`GET /api/v1/diagnostics/status`.

Status must confirm the key is loaded **without echoing it**
(`openai_api_key_loaded` boolean only).

## Query-time flow

`POST /api/v1/diagnostics/root-cause`

```json
{
  "asset_id": "compressor-17",
  "symptom_summary": "High vibration and bearing temperature on compressor 17 during line 1 production ramp.",
  "recent_alert_ids": []
}
```

`app/services/rag.py`:

1. `prediction_service.get_latest(asset_id)` (404 if no telemetry).
2. Map `dominant_signal` → `ISSUE_PLAYBOOK` query terms / fallback causes.
3. Build retrieval query from asset context, symptom, signal, playbook terms.
4. `knowledge_service.retrieve` (OpenAI query embedding when available, else
   TF-IDF). Limit `AURAVANCE_RAG_RETRIEVAL_LIMIT` (default 5).
5. Call OpenAI Responses API (`AURAVANCE_RAG_RESPONSE_MODEL`, default
   `gpt-4.1-mini`, temperature 0.2) with structured JSON schema.
6. On missing key or API error, `_fallback_response`: sentences extracted
   from chunks via cause/action keywords, plus playbook.

Return fields: `grounded_summary`, `likely_causes`, `recommended_actions`,
`confidence`, `generation_mode`, `generation_model`, `evidence_snippets`.

## Grounding rules (do not relax)

Instructions in `openai_client.generate_root_cause_analysis`:

- Reliability-engineer persona.
- JSON only, schema-enforced.
- Use **only** retrieved evidence and supplied prediction context.
- Do not invent manuals, asset facts, or maintenance steps.

If evidence is empty, say so and use the playbook with `confidence: low`.
Never fabricate a PDF citation.

## Frontend

Root Cause Analysis nav builds `symptom_summary` from the latest prediction
and recent alerts (`buildRootCauseSymptomSummary` in `App.jsx`). Keep that
helper in sync if prediction fields change.

## When extending

- New equipment class: add a markdown guide under `knowledge/`,
  playbook entry for its `dominant_signal`, re-run `prepare_knowledge.py`.
- Vector DB upgrade: pgvector is the documented target. Keep the retrieve
  function signature so `rag.py` does not care about the backend.
- Do not call the LLM from ingest/scoring. Diagnostics stay request-driven
  so telemetry latency stays sub-minute without token spend.
