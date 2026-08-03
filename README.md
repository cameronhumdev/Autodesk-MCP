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

## Quick start — full demo

1. Approve **UAC** if Docker install prompts.  
2. Double-click [`demo/start-demo.bat`](./demo/start-demo.bat)

| UI | URL |
|----|-----|
| AnythingLLM (K8s NodePort) | http://localhost:30080 |
| AnythingLLM (Compose fallback) | http://localhost:3080 |
| Custom test UI | http://127.0.0.1:8080 via `test-ui\start.bat` |

Details: [`demo/README.md`](./demo/README.md)

## Defaults (OSS)

| Piece | Choice | License |
|-------|--------|---------|
| Inventor MCP (v2) | ipt-mcp | Apache-2.0 |
| AutoCAD MCP (v2) | U-C4N | MIT |
| RAG product | AnythingLLM | MIT |
| Local test RAG | `rag/local` | this repo |
| Orchestration | Kubernetes | Apache-2.0 |
| Infra | OpenTofu | MPL-2.0 |
