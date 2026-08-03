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
| http://localhost:8080 | test-ui |
| http://localhost:3080 | AnythingLLM |

Windows: use `test-ui\start.bat` / `start-anythingllm.bat`.

## Files

| File | Purpose |
|------|---------|
| `compose.yml` | Local test-ui |
| `compose.anythingllm.yml` | AnythingLLM |
| `Dockerfile.test-ui` | Image for `test-ui/` |

## Env

See `test-ui/.env.example`. Compose passes them into the container.
