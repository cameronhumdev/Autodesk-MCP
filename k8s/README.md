# `k8s/` — Kubernetes

| Path | Purpose |
|------|---------|
| `anythingllm/` | Demo: AnythingLLM in namespace `autodesk-mcp-demo` |
| `test-ui/` | Optional smoke Deployment for our test UI |

## Demo apply

Prefer: `demo\start-demo.bat`

Manual:

```bash
kubectl apply -k k8s/anythingllm
# UI via NodePort:
# http://localhost:30080
```

## Requires

- Docker Desktop with **Kubernetes enabled**, or any kubeconfig cluster
- Ollama on the host for local models (`host.docker.internal:11434`)
