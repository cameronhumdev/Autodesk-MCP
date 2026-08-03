# AnythingLLM backend (cloud default)

| Item | Value |
|------|--------|
| Upstream | https://github.com/Mintplex-Labs/anything-llm |
| License | MIT |
| Deploy | Docker image on Kubernetes (see `k8s/`, `docker/`) |

## Status

Hook folder for the production RAG. v1 test UI uses `rag/local` so you can chat without standing up AnythingLLM first.

## Swap in later

1. Run AnythingLLM via `docker/` or `k8s/`.
2. Implement HTTP client against its API in `client.py` (add when ready).
3. Set `RAG_BACKEND=anythingllm`.
