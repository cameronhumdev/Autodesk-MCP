# `docker/` — Images & local Compose

| Item | Value |
|------|--------|
| Role | Build images; local spin-up (laptop / WSL2) |
| Production orchestration | Kubernetes (`../k8s/`) — not Compose |
| Swap | Change Dockerfiles / compose services; keep image names stable where possible |

## Quick start

```bash
cd docker
# Custom test UI image
docker compose up --build

# AnythingLLM (official image)
docker compose -f compose.anythingllm.yml up -d
```

| URL | Service |
|-----|---------|
| http://127.0.0.1:8787 | test-ui |
| http://127.0.0.1:3188 | AnythingLLM |

Windows: use `test-ui\start.bat` / `start-anythingllm.bat`.

## Files

| File | Purpose |
|------|---------|
| `compose.yml` | Local test-ui |
| `compose.anythingllm.yml` | AnythingLLM |
| `Dockerfile.test-ui` | Image for `test-ui/` |

## Env

See `test-ui/.env.example`. Compose passes them into the container.
