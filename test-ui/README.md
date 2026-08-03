# `test-ui/` — Local chat + tool playground

Small UI to spin up, chat with an LLM, run sample actions, and hit local RAG.

| Item | Value |
|------|--------|
| Stack | FastAPI + static HTML |
| LLM | OpenAI-compatible API (Ollama or cloud) |
| RAG | `rag/local` by default (swappable) |
| CAD | Mock tools only (v1) |

## Run (Windows)

| Script | Opens |
|--------|--------|
| `start.bat` | Custom test UI → http://127.0.0.1:8080 |
| `start-anythingllm.bat` | AnythingLLM (Docker) → http://localhost:3080 |
| `setup-openai.bat` | Put OpenAI API key into `.env` (live chat) |
| `setup-ollama.bat` | Point `.env` at local Ollama |
| `stop-anythingllm.bat` | Stop AnythingLLM |

Compare both: [`../docs/TEST-BOTH-UIS.md`](../docs/TEST-BOTH-UIS.md)

Close the custom UI console window to stop that server.

## Run (manual / WSL)

```bash
# from repo root
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r test-ui/requirements.txt
cp test-ui/.env.example test-ui/.env
uvicorn test_ui_app.main:app --app-dir test-ui --reload --port 8080
```

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
