# Autodesk MCP + RAG

Modular cloud AI stack: cloneable RAG, Docker images, Kubernetes, Terraform, Autodesk MCPs (v2), and a local test UI.

## Modules

| Folder | Role | Swap? |
|--------|------|-------|
| [`rag/`](./rag/) | Knowledge / private-public AI adapters | Yes — `RAG_BACKEND` |
| [`docker/`](./docker/) | Images + local Compose | Yes |
| [`k8s/`](./k8s/) | Kubernetes manifests | Yes |
| [`terraform/`](./terraform/) | OpenTofu/Terraform modules | Yes |
| [`mcp/`](./mcp/) | Inventor / AutoCAD MCP (v2) | Yes |
| [`test-ui/`](./test-ui/) | Chat UI + mock tools + samples | Dev harness |

**Plan:** [PLAN.md](./PLAN.md)

## Quick start — test UI

```bash
# WSL2 Ubuntu / Linux — from repo root
python -m venv .venv
source .venv/bin/activate
pip install -r test-ui/requirements.txt
cp test-ui/.env.example test-ui/.env
uvicorn test_ui_app.main:app --app-dir test-ui --reload --port 8080
```

Or:

```bash
cd docker && docker compose up --build
```

Open http://localhost:8080 — samples from [`test-ui/SAMPLES.md`](./test-ui/SAMPLES.md) appear in the sidebar.

Works in **demo mode** without Ollama/OpenAI (mock LLM + real mock tools + local RAG).

## Defaults (OSS)

| Piece | Choice | License |
|-------|--------|---------|
| Inventor MCP (v2) | ipt-mcp | Apache-2.0 |
| AutoCAD MCP (v2) | U-C4N | MIT |
| RAG product | AnythingLLM | MIT |
| Local test RAG | `rag/local` | this repo |
| Orchestration | Kubernetes | Apache-2.0 |
| Infra | OpenTofu | MPL-2.0 |
