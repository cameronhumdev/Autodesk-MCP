# `test-ui/` — Local chat + tool playground

Small UI to spin up, chat with an LLM, run sample actions, and hit local RAG.

| Item | Value |
|------|--------|
| Stack | FastAPI + static HTML |
| LLM | OpenAI-compatible API (Ollama or cloud) |
| RAG | `rag/local` by default (swappable) |
| CAD | Mock tools only (v1) |

## Run (no Docker)

```bash
# from repo root
python -m venv .venv
# Windows: .venv\Scripts\activate
# WSL/Ubuntu:
source .venv/bin/activate
pip install -r test-ui/requirements.txt
cp test-ui/.env.example test-ui/.env
# edit test-ui/.env — set LLM_BASE_URL / LLM_MODEL / LLM_API_KEY
uvicorn test_ui_app.main:app --app-dir test-ui --reload --port 8080
```

Open http://localhost:8080

## Run (Docker)

```bash
cd docker
docker compose up --build
```

## Samples

Editable demos: [`SAMPLES.md`](./SAMPLES.md) — also listed in the UI sidebar.

## Swap points

| Concern | Env / module |
|---------|----------------|
| LLM host | `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` |
| RAG | `RAG_BACKEND` → `rag/` |
| Tools | `test_ui_app/tools.py` |
