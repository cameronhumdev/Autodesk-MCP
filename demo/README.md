# Demo stack

One-command local demo: **Docker + Kubernetes + AnythingLLM + Ollama**.

## You do once

1. Approve **UAC** if Docker Desktop installer asks.
2. Install [Ollama](https://ollama.com) if missing, then leave it running.
3. After Docker is up, double-click:

```text
demo\start-demo.bat
```

## What the script does

1. Starts Docker Desktop if needed  
2. Enables Kubernetes (Docker Desktop)  
3. Pulls `qwen2.5:7b` into Ollama  
4. Deploys AnythingLLM into K8s namespace `autodesk-mcp-demo`  
5. Opens the UI  

| Service | URL |
|---------|-----|
| AnythingLLM | http://localhost:30080 |
| Fallback Compose | http://127.0.0.1:3188 (`demo\start-demo-compose.bat`) |
| Our test UI | http://127.0.0.1:8787 (`test-ui\start.bat`) |

## In the AnythingLLM UI (only manual step)

1. Finish onboarding if shown  
2. Confirm LLM = **Ollama** / model **qwen2.5:7b**  
3. Create a workspace → upload a PDF → chat  

## Stop

```text
demo\stop-demo.bat
```
