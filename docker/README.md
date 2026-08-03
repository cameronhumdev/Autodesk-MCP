# `docker/` — Images & local Compose

| Item | Value |
|------|--------|
| Role | Build images; local spin-up (laptop / WSL2) |
| Production orchestration | Kubernetes (`../k8s/`) — not Compose |
| Swap | Change Dockerfiles / compose services; keep image names stable where possible |

## Quick start (test UI)

```bash
# from repo root (WSL2 Ubuntu or Linux)
cd docker
cp ../test-ui/.env.example ../test-ui/.env   # edit LLM settings
docker compose up --build
```

Open http://localhost:8080

## Files

| File | Purpose |
|------|---------|
| `compose.yml` | Local stack: test-ui (+ optional ollama) |
| `Dockerfile.test-ui` | Image for `test-ui/` |

## Env

See `test-ui/.env.example`. Compose passes them into the container.
